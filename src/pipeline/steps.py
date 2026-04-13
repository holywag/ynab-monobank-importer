"""Pipeline step implementations and registry.

Steps are registered by name and instantiated from YAML config.
Each step is a callable: Iterable[YnabTransaction] -> Iterable[YnabTransaction].
"""

from collections.abc import Iterable
from datetime import datetime

import yaml

from model.transaction import YnabTransaction
from model.configuration import (
    PipelineContext, YnabAccountRef, YnabCategory, RegexDict,
)
from sources import BankApiSource
from config.loader import resolve_time_range, compile_pattern
from filters.transfer_filter import TransferFilter
import ynab_api, ynab


# --- Registry ---

_FILTERS: dict[str, type] = {}
_MAPPERS: dict[str, type] = {}


def register_filter(name):
    """Register a filter callable by name for use in pipeline YAML."""
    def decorator(cls):
        _FILTERS[name] = cls
        return cls
    return decorator


def register_mapper(name):
    """Register a mapper callable by name for use in pipeline YAML."""
    def decorator(cls):
        _MAPPERS[name] = cls
        return cls
    return decorator


# --- Built-in filters ---

@register_filter('deduplicate_transfers')
class DeduplicateTransfersFilter:
    """Removes duplicate transfer transactions between YNAB accounts."""
    def __init__(self, **kwargs):
        self._filter = TransferFilter()

    def __call__(self, t: YnabTransaction) -> bool:
        return self._filter(t)


# --- Built-in mappers ---

@register_mapper('payee')
class PayeeMapper:
    """Maps transaction payee using regex aliases from a YAML file."""
    def __init__(self, mappings: str, **kwargs):
        with open(mappings) as f:
            payees_data = yaml.safe_load(f)
        self._payee_map = RegexDict(
            (compile_pattern(*regexes), alias)
            for alias, regexes in payees_data.items()
            if regexes
        )

    def __call__(self, t: YnabTransaction) -> YnabTransaction:
        mapped = self._payee_map.get(t.description)
        if mapped:
            t.payee = mapped
        return t


@register_mapper('categorize')
class CategorizeMapper:
    """Maps transaction category using payee/MCC rules from a YAML file."""
    def __init__(self, mappings: str, **kwargs):
        with open(mappings) as f:
            categories_data = yaml.safe_load(f)
        self._by_payee = RegexDict(
            (compile_pattern(*entry['match']['payee']), YnabCategory(**entry['category']))
            for entry in categories_data
            if entry.get('match', {}).get('payee')
        )
        self._by_mcc = {
            mcc: YnabCategory(**entry['category'])
            for entry in categories_data
            for mcc in entry.get('match', {}).get('mcc', [])
        }

    def __call__(self, t: YnabTransaction) -> YnabTransaction:
        if not t.category:
            t.category = self._by_payee.get(t.description) or self._by_mcc.get(t.mcc)
        return t


@register_mapper('change_date')
class ChangeDataMapper:
    """Alters transaction date."""
    def __init__(self, year = None, **kwargs):
        self.year = year
    
    def __call__(self, t: ynab.TransactionDetail) -> YnabTransaction:
        if self.year:
            t.var_date = t.var_date.replace(year=self.year)
        return t
        

# TODO: register_mapper('currency_convert') — convert amounts between currencies
# TODO: register_mapper('adjust_dates') — shift transaction dates
# TODO: register_filter('by_payee') — filter by payee pattern
# TODO: register_filter('by_category') — filter by category


# --- Step builders ---

def build_steps(step_dicts: list[dict], ctx: PipelineContext) -> list:
    """Build executable step callables from pipeline YAML config."""
    steps = []
    for step_dict in step_dicts:
        for step_type, params in step_dict.items():
            match step_type:
                case 'read':
                    steps.append(_build_read(ctx, params))
                case 'filter':
                    steps.append(_build_filter(params))
                case 'map':
                    steps.append(_build_map(params))
                case 'write':
                    steps.append(_build_write(ctx, params))
                case _:
                    raise ValueError(f'Unknown pipeline step type: {step_type}')
    return steps


def _parse_account_mapping(
    mapping_dict: dict[str, str], ctx: PipelineContext,
) -> dict[str, YnabAccountRef]:
    """Parse 'source.account: budget.ynab_name' mapping into YnabAccountRef dict."""
    result = {}
    for source_account, budget_ynab in mapping_dict.items():
        budget_key, ynab_name = budget_ynab.split('.', 1)
        result[source_account] = YnabAccountRef(
            name=ynab_name, budget=ctx.budgets[budget_key])
    return result

def _build_read_from_source(ctx: PipelineContext, params: dict):
    """Build a read step that creates transaction streams from sources."""
    from_mapping = params['from_source']
    tracking_mapping = params.get('tracking', {})
    time_range_cfg = params.get('time_range')

    # Parse both from and tracking into ynab mappings
    ynab_mapping = _parse_account_mapping(from_mapping, ctx)
    ynab_mapping.update(_parse_account_mapping(tracking_mapping, ctx))

    # Build transfer pattern matching from ALL mapped accounts
    all_mapped_accounts = [ctx.accounts[key] for key in ynab_mapping]
    transfer_patterns = RegexDict(
        (a.transfer_payee, a) for a in all_mapped_accounts if a.transfer_payee
    )

    read_accounts = set(from_mapping.keys())
    source_names = {key.split('.', 1)[0] for key in read_accounts}

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        tr = resolve_time_range(time_range_cfg) if time_range_cfg else None
        for source_name in source_names:
            if source_name not in ctx.source_configs:
                continue
            src = BankApiSource(
                ctx.source_configs[source_name], transfer_patterns, tr,
                ynab_mapping, read_accounts)
            yield from src.read()

    return step

def _build_read_from_budget(ctx: PipelineContext, params: dict):
    """Build a read step that creates transaction streams from budget."""
    time_range_cfg = params.get('time_range')
        
    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        tr = resolve_time_range(time_range_cfg) if time_range_cfg else None
        for budget_key, accounts in params['from_budget'].items():
            budget = ctx.budgets[budget_key]
            ynab = ynab_api.SingleBudgetYnabApiWrapper(
                ynab_api.YnabApiWrapper(budget.token), budget.budget_name)
            for acc in accounts:
                yield from ynab.get_transactions_by_account(acc, tr.start.date())

    return step


def _build_read(ctx: PipelineContext, params: dict):
    """Build a read step that creates transaction stream."""
    if 'from_source' in params:
        return _build_read_from_source(ctx, params)
    elif 'from_budget' in params:
        return _build_read_from_budget(ctx, params)
    else:
        raise Exception(f'Cannot recoginze read params {params.keys()}')


def _build_filter(params):
    """Build a filter step from registry."""
    if isinstance(params, str):
        name, kwargs = params, {}
    else:
        kwargs = dict(params)
        name = kwargs.pop('type')

    filter_fn = _FILTERS[name](**kwargs)

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        return filter(filter_fn, stream)

    return step


def _build_map(params):
    """Build a map step from registry."""
    if isinstance(params, str):
        name, kwargs = params, {}
    else:
        kwargs = dict(params)
        name = kwargs.pop('type')

    map_fn = _MAPPERS[name](**kwargs)

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        return map(map_fn, stream)

    return step


def _build_write(ctx: PipelineContext, params: dict):
    """Build a write step that sends transactions to a YNAB budget."""
    budget_key = params['to']
    budget = ctx.budgets[budget_key]
    timestamp_file = params.get('timestamp')

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        ynab = ynab_api.SingleBudgetYnabApiWrapper(
            ynab_api.YnabApiWrapper(budget.token), budget.budget_name)
        transactions = list(stream)
        print(f'Sending {len(transactions)} transactions to "{budget.budget_name}"...')
        result = ynab.update_transactions(transactions)
        if result:
            print(f'-- Imported: {len(result.transaction_ids)}')
        else:
            print('-- Nothing to import')
        if timestamp_file:
            with open(timestamp_file, 'w') as f:
                f.write(datetime.now().astimezone().isoformat())
            print(f'Saved timestamp to {timestamp_file}')
        return iter(transactions)

    return step
