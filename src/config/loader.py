"""Load and validate YAML configuration, producing PipelineContext."""

import os
import re
from datetime import datetime

import yaml
from dotenv import load_dotenv

load_dotenv()

from .schema import (
    RootConfig, BudgetConfig, SourceConfig,
    MonobankSourceConfig, TrackingSourceConfig,
)
from model.configuration import (
    BankAccountConfiguration, BankApiConfiguration, BankApiName,
    PipelineContext, ResolvedBudget, TimeRange,
)


def load(config_path: str = 'config/config.yaml') -> PipelineContext:
    """Load YAML config, validate with Pydantic, build PipelineContext."""
    with open(config_path) as f:
        raw = _resolve_env_vars(yaml.safe_load(f))

    schema = RootConfig.model_validate(raw)
    sources_data = _load_yaml(schema.sources) if isinstance(schema.sources, str) else schema.sources
    budgets_data = _load_yaml(schema.budgets) if isinstance(schema.budgets, str) else schema.budgets

    # Validate sources against schema
    sources_validated: dict[str, SourceConfig] = {
        k: _validate_source(v) for k, v in sources_data.items()
    }

    # Build accounts and source configs
    all_accounts: dict[str, BankAccountConfiguration] = {}
    source_configs: dict[str, BankApiConfiguration] = {}

    for source_id, src_cfg in sources_validated.items():
        source_accounts = []
        for acc_id, acc_cfg in src_cfg.accounts.items():
            acc = BankAccountConfiguration(
                name=acc_id,
                source_name=source_id,
                iban=acc_cfg.iban,
                transfer_payee=compile_pattern(*acc_cfg.transfer_patterns) if acc_cfg.transfer_patterns else None,
            )
            all_accounts[f'{source_id}.{acc_id}'] = acc
            source_accounts.append(acc)

        if isinstance(src_cfg, TrackingSourceConfig):
            continue

        if isinstance(src_cfg, MonobankSourceConfig):
            source_configs[source_id] = BankApiConfiguration(
                type=BankApiName(src_cfg.type),
                name=source_id,
                token=src_cfg.token,
                n_retries=src_cfg.retries,
                remove_cancelled_statements=src_cfg.remove_cancelled,
                accounts=source_accounts,
            )
        else:
            source_configs[source_id] = BankApiConfiguration(
                type=BankApiName(src_cfg.type),
                name=source_id,
                token=src_cfg.path,
                n_retries=0,
                remove_cancelled_statements=False,
                accounts=source_accounts,
            )

    # Build resolved budgets
    budgets = {}
    for budget_key, budget in budgets_data.items():
        budget_cfg = budget if isinstance(budget, BudgetConfig) else BudgetConfig.model_validate(budget)
        budgets[budget_key] = ResolvedBudget(
            token=budget_cfg.token,
            budget_name=budget_cfg.budget,
        )

    return PipelineContext(
        accounts=all_accounts,
        source_configs=source_configs,
        budgets=budgets,
        pipeline_paths=dict(schema.pipelines),
    )


def load_pipeline(pipeline_path: str) -> list[dict]:
    """Load pipeline step definitions from YAML."""
    with open(pipeline_path) as f:
        raw = yaml.safe_load(f)
    return raw['steps']


def resolve_time_range(time_range_config: dict) -> TimeRange:
    """Resolve a time_range config dict into a TimeRange domain object.

    `start` is either an ISO datetime string or a file path containing one.
    If it's a file path, the file must exist (raises FileNotFoundError).
    `end` is an optional ISO datetime string; null means now.
    """
    start_raw = time_range_config['start']
    end = time_range_config.get('end')

    try:
        datetime.fromisoformat(start_raw)
        start = start_raw
    except (ValueError, TypeError):
        with open(start_raw) as f:
            start = f.read().strip()

    time_range_start = datetime.fromisoformat(start)
    return TimeRange(
        start=time_range_start,
        end=datetime.fromisoformat(end) if end else datetime.now(tz=time_range_start.tzinfo),
    )


def compile_pattern(*regex_str_list: str) -> re.Pattern | None:
    """Compile multiple regex strings into a single alternation pattern."""
    if not regex_str_list:
        return None
    return re.compile(f'(?:{"|".join(regex_str_list)})')


# --- Internal helpers ---

def _validate_source(data: dict) -> SourceConfig:
    """Validate a raw source dict against the appropriate Pydantic model."""
    from pydantic import TypeAdapter
    adapter = TypeAdapter(SourceConfig)
    return adapter.validate_python(data)


_ENV_VAR_PATTERN = re.compile(r'\$\{(\w+)\}')


def _resolve_env_vars(obj):
    """Recursively resolve ${ENV_VAR} references in strings."""
    if isinstance(obj, str):
        def _replace(match):
            var = match.group(1)
            value = os.environ.get(var)
            if value is None:
                raise ValueError(f'Environment variable ${{{var}}} is not set')
            return value
        return _ENV_VAR_PATTERN.sub(_replace, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(v) for v in obj]
    return obj


def _load_yaml(path: str):
    with open(path) as f:
        return _resolve_env_vars(yaml.safe_load(f))
