"""Load and validate YAML configuration, producing domain objects."""

import json
import re
from copy import copy
from datetime import datetime
from pathlib import Path

import yaml

from .schema import RootConfig, MonobankSourceConfig
from model.configuration import (
    BankAccountConfiguration, BankApiConfiguration, BankApiName,
    Configuration, RegexDict, StatementFieldMappings,
    TimeRange, YnabCategory, YnabCategoryMappings, YnabConfiguration,
)

TIMESTAMP_FILE = './config/timestamp.json'


def load(config_path: str = 'config/config.yaml') -> Configuration:
    """Load YAML config, validate with Pydantic, build domain Configuration."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    schema = RootConfig.model_validate(raw)

    # Build account identity objects
    accounts: dict[str, BankAccountConfiguration] = {}
    for acc_id, acc_cfg in schema.accounts.items():
        patterns = list(acc_cfg.transfer_patterns)
        if acc_cfg.ynab_name:
            patterns.append('Transfer : ' + re.escape(acc_cfg.ynab_name))
        accounts[acc_id] = BankAccountConfiguration(
            enabled=False,
            ynab_name=acc_cfg.ynab_name,
            iban=acc_cfg.iban,
            transfer_payee=_compile_pattern(*patterns),
        )

    # Build bank API configurations
    apis: list[BankApiConfiguration] = []
    for source_id, src_cfg in schema.sources.items():
        source_accounts = []
        for acc_id, enabled in src_cfg.accounts.items():
            acc = copy(accounts[acc_id])
            acc.enabled = enabled
            # Replace shared account object so source has its own copy with correct enabled
            accounts[acc_id] = acc
            source_accounts.append(acc)

        if isinstance(src_cfg, MonobankSourceConfig):
            apis.append(BankApiConfiguration(
                name=BankApiName(src_cfg.type),
                token=src_cfg.token,
                n_retries=src_cfg.retries,
                remove_cancelled_statements=src_cfg.remove_cancelled,
                accounts=source_accounts,
            ))
        else:
            apis.append(BankApiConfiguration(
                name=BankApiName(src_cfg.type),
                token=src_cfg.path,  # filesystem path stored in token field for backward compat
                n_retries=0,
                remove_cancelled_statements=False,
                accounts=source_accounts,
            ))

    # Load mappings for target budget
    budget_key = schema.pipeline.target_budget
    budget_cfg = schema.ynab[budget_key]

    categories_data = _load_yaml(budget_cfg.mappings.categories)
    payees_data = _load_yaml(budget_cfg.mappings.payees)

    all_accounts = list(accounts.values())
    mappings = _build_mappings(all_accounts, categories_data, payees_data)

    # Time range
    timestamp_json = None
    if schema.time_range.use_last_import:
        try:
            with open(TIMESTAMP_FILE) as f:
                timestamp_json = json.load(f)
        except FileNotFoundError:
            pass

    time_range = _build_time_range(
        schema.time_range.start,
        schema.time_range.end,
        timestamp_json if schema.time_range.use_last_import else None,
    )

    return Configuration(
        merge_transfer_statements=schema.pipeline.merge_transfer_statements,
        remember_last_import_timestamp=schema.time_range.use_last_import,
        time_range=time_range,
        apis=apis,
        ynab=YnabConfiguration(token=budget_cfg.token, budget_name=budget_cfg.budget),
        mappings=mappings,
    )


def _load_yaml(path: str):
    with open(path) as f:
        return yaml.safe_load(f)


def _compile_pattern(*regex_str_list: str) -> re.Pattern | None:
    if not regex_str_list:
        return None
    return re.compile(f'(?:{"|".join(regex_str_list)})')


def _build_time_range(start: str, end: str | None, timestamp_json: dict | None) -> TimeRange:
    last_import = timestamp_json and datetime.fromisoformat(timestamp_json['last_import'])
    time_range_start = datetime.fromisoformat(start)
    if last_import and last_import > time_range_start:
        time_range_start = last_import
    return TimeRange(
        start=time_range_start,
        end=datetime.fromisoformat(end) if end else datetime.now(tz=time_range_start.tzinfo),
    )


def _build_mappings(
    all_accounts: list[BankAccountConfiguration],
    categories_data: list[dict],
    payees_data: dict[str, list[str]],
) -> StatementFieldMappings:
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
                (_compile_pattern(*entry['match']['payee']), YnabCategory(**entry['category']))
                for entry in categories_data
                if entry.get('match', {}).get('payee')
            ),
        ),
        payee=RegexDict(
            (_compile_pattern(*regexes), alias)
            for alias, regexes in payees_data.items()
            if regexes
        ),
    )
