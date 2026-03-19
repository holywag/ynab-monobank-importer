"""Load and validate YAML configuration, producing PipelineContext."""

import re
from datetime import datetime

import yaml

from .schema import (
    RootConfig, BudgetConfig, SourceConfig,
    MonobankSourceConfig, TrackingSourceConfig,
)
from model.configuration import (
    BankAccountConfiguration, BankApiConfiguration, BankApiName,
    PipelineContext, RegexDict, ResolvedBudget, StatementFieldMappings,
    TimeRange, YnabCategory, YnabCategoryMappings,
)


def load(config_path: str = 'config/config.yaml') -> PipelineContext:
    """Load YAML config, validate with Pydantic, build PipelineContext."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    schema = RootConfig.model_validate(raw)
    sources_data = _load_yaml(schema.sources)
    budgets_data = _load_yaml(schema.budgets)

    # Validate sources against schema
    sources_validated: dict[str, SourceConfig] = {
        k: _validate_source(k, v) for k, v in sources_data.items()
    }

    # Build accounts and source configs from sources section
    all_accounts: dict[str, BankAccountConfiguration] = {}
    source_configs: dict[str, BankApiConfiguration] = {}

    for source_id, src_cfg in sources_validated.items():
        source_accounts = []
        for acc_id, acc_cfg in src_cfg.accounts.items():
            patterns = list(acc_cfg.transfer_patterns)
            if acc_cfg.ynab_name:
                patterns.append('Transfer : ' + re.escape(acc_cfg.ynab_name))
            acc = BankAccountConfiguration(
                enabled=acc_cfg.enabled,
                ynab_name=acc_cfg.ynab_name,
                iban=acc_cfg.iban,
                transfer_payee=compile_pattern(*patterns) if patterns else None,
            )
            all_accounts[acc_id] = acc
            source_accounts.append(acc)

        if isinstance(src_cfg, TrackingSourceConfig):
            # Tracking accounts participate in transfer detection only
            continue

        if isinstance(src_cfg, MonobankSourceConfig):
            source_configs[source_id] = BankApiConfiguration(
                name=BankApiName(src_cfg.type),
                token=src_cfg.token,
                n_retries=src_cfg.retries,
                remove_cancelled_statements=src_cfg.remove_cancelled,
                accounts=source_accounts,
            )
        else:
            source_configs[source_id] = BankApiConfiguration(
                name=BankApiName(src_cfg.type),
                token=src_cfg.path,
                n_retries=0,
                remove_cancelled_statements=False,
                accounts=source_accounts,
            )

    # Build resolved budgets
    budgets = _build_budgets(budgets_data, all_accounts)

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

    return _build_time_range(start, end)


def compile_pattern(*regex_str_list: str) -> re.Pattern | None:
    """Compile multiple regex strings into a single alternation pattern."""
    if not regex_str_list:
        return None
    return re.compile(f'(?:{"|".join(regex_str_list)})')


# --- Internal helpers ---

def _validate_source(_name: str, data: dict) -> SourceConfig:
    """Validate a raw source dict against the appropriate Pydantic model."""
    # Pydantic discriminated union handles type dispatch
    from pydantic import TypeAdapter
    adapter = TypeAdapter(SourceConfig)
    return adapter.validate_python(data)


def _load_yaml(path: str):
    with open(path) as f:
        return yaml.safe_load(f)


def _build_time_range(start: str, end: str | None) -> TimeRange:
    time_range_start = datetime.fromisoformat(start)
    return TimeRange(
        start=time_range_start,
        end=datetime.fromisoformat(end) if end else datetime.now(tz=time_range_start.tzinfo),
    )


def _build_budgets(
    budgets_data: dict, all_accounts: dict[str, BankAccountConfiguration],
) -> dict[str, ResolvedBudget]:
    budgets = {}
    for budget_key, budget in budgets_data.items():
        budget_cfg = BudgetConfig.model_validate(budget)
        categories_data = _load_yaml(budget_cfg.mappings.categories)
        payees_data = _load_yaml(budget_cfg.mappings.payees)

        accounts_list = list(all_accounts.values())
        mappings = _build_mappings(accounts_list, categories_data, payees_data)

        budgets[budget_key] = ResolvedBudget(
            token=budget_cfg.token,
            budget_name=budget_cfg.budget,
            mappings=mappings,
        )
    return budgets


def _build_mappings(all_accounts, categories_data, payees_data) -> StatementFieldMappings:
    return StatementFieldMappings(
        account_by_transfer_payee=RegexDict(
            (a.transfer_payee, a) for a in all_accounts if a.transfer_payee
        ),
        category=YnabCategoryMappings(
            by_mcc={
                mcc: YnabCategory(**entry['category'])
                for entry in categories_data
                for mcc in entry.get('match', {}).get('mcc', [])
            },
            by_payee=RegexDict(
                (compile_pattern(*entry['match']['payee']), YnabCategory(**entry['category']))
                for entry in categories_data
                if entry.get('match', {}).get('payee')
            ),
        ),
        payee=RegexDict(
            (compile_pattern(*regexes), alias)
            for alias, regexes in payees_data.items()
            if regexes
        ),
    )
