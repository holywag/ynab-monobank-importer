"""Pipeline step implementations and registry.

Steps are registered by name and instantiated from YAML config.
Each step is a callable: Iterable[YnabTransaction] -> Iterable[YnabTransaction].
"""

from collections.abc import Iterable
from datetime import datetime

from model.transaction import YnabTransaction
from model.configuration import (
    PipelineContext, YnabAccountRef, RegexDict, StatementFieldMappings,
)
from sources import BankApiSource
from config.loader import resolve_time_range
from filters.transfer_filter import TransferFilter
import ynab_api


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
                    steps.append(_build_filter(ctx, params))
                case 'map':
                    steps.append(_build_map(ctx, params))
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


def _build_read(ctx: PipelineContext, params: dict):
    """Build a read step that creates transaction streams from sources."""
    from_mapping = params['from']           # accounts to read from
    transfer_mapping = params.get('tracking', {})  # transfer-detection-only accounts
    time_range_cfg = params.get('time_range')
    mappings_key = params.get('mappings')

    # Parse both from and transfers into ynab mappings
    ynab_mapping = _parse_account_mapping(from_mapping, ctx)
    ynab_mapping.update(_parse_account_mapping(transfer_mapping, ctx))

    # Build transfer pattern matching from ALL mapped accounts
    all_mapped_accounts = [ctx.accounts[key] for key in ynab_mapping]
    transfer_patterns = RegexDict(
        (a.transfer_payee, a) for a in all_mapped_accounts if a.transfer_payee
    )

    # Collect unique source names and read account keys
    read_accounts = set(from_mapping.keys())
    source_names = {key.split('.', 1)[0] for key in read_accounts}

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        tr = resolve_time_range(time_range_cfg) if time_range_cfg else None
        budget = ctx.budgets[mappings_key] if mappings_key else None
        mappings = StatementFieldMappings(
            account_by_transfer_payee=transfer_patterns,
            category=budget.category_mappings,
            payee=budget.payee_mappings,
        )
        for source_name in source_names:
            if source_name not in ctx.source_configs:
                continue  # tracking source
            src = BankApiSource(
                ctx.source_configs[source_name], mappings, tr,
                ynab_mapping, read_accounts)
            yield from src.read()

    return step


def _build_filter(ctx: PipelineContext, params):
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


def _build_map(ctx: PipelineContext, params):
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
        result = ynab.create_transactions(transactions)
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
