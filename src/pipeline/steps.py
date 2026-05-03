"""Pipeline step implementations and registry.

Steps are registered by name and instantiated from YAML config.
Each step is a callable: Iterable[YnabTransaction] -> Iterable[YnabTransaction].
"""

from collections.abc import Iterable
from datetime import datetime

import yaml, re

from utils.exchange_rates import init_rates_cache, Currency
from model.transaction import YnabTransaction
from model.configuration import PipelineContext, YnabAccountRef, RegexDict
from sources import BankApiSource
from config.loader import resolve_time_range, compile_pattern
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
        payee_name = t.detail.payee_name or ''
        mapped = self._payee_map.get(payee_name)
        if mapped:
            t.detail.payee_name = mapped
        return t


@register_mapper('categorize')
class CategorizeMapper:
    """Maps transaction category using payee/MCC rules from a YAML file.
    Resolves category_id via YNAB API."""
    def __init__(self, mappings: str, budget: str, ctx: PipelineContext, **kwargs):
        with open(mappings) as f:
            categories_data = yaml.safe_load(f)
        self._by_payee = RegexDict(
            (compile_pattern(*entry['match']['payee']), entry['category'])
            for entry in categories_data
            if entry.get('match', {}).get('payee')
        )
        self._by_mcc = {
            mcc: entry['category']
            for entry in categories_data
            for mcc in entry.get('match', {}).get('mcc', [])
        }
        # Pre-fetch category tree for ID resolution
        budget_cfg = ctx.budgets[budget]
        self._ynab = ynab_api.SingleBudgetYnabApiWrapper(
            ynab_api.YnabApiWrapper(budget_cfg.token), budget_cfg.budget_name)

    def __call__(self, t: YnabTransaction) -> YnabTransaction:
        if not t.detail.category_id:
            payee_name = t.detail.payee_name or ''
            mcc = t.bank_transaction.mcc if t.bank_transaction else None
            cat = self._by_payee.get(payee_name) or (self._by_mcc.get(mcc) if mcc else None)
            if cat:
                t.detail.category_id = self._ynab.get_category_id_by_name(cat['group'], cat['name'])
        return t


@register_mapper('change_date')
class ChangeDateMapper:
    """Alters transaction date."""
    def __init__(self, year=None, **kwargs):
        self.year = year

    def __call__(self, t: YnabTransaction) -> YnabTransaction:
        if self.year:
            t.detail.var_date = t.detail.var_date.replace(year=self.year)
        return t


@register_filter('pre_filter_to_convert_to_uah_by_memo')
class PreFilterConvertToEurByMemo:
    # group(2) is the extracted value
    RE=re.compile(r'^(€)?([0-9]+?(\.[0-9]+)?)$')
    
    def __init__(self, *args, **kwargs):
        pass
    
    def __call__(self, t: YnabTransaction) -> bool:
        # Skip transfers
        if t.detail.transfer_account_id:
            return False
        # Skip splits (for now)
        if t.detail.subtransactions:
            return False
        # Skip transactions with any existing amount.
        # Should be 0 to be eligible for conversion.
        if t.detail.amount:
            return False
        # Skip not matching transactions
        if not self.RE.match(t.detail.memo.replace(',', '')):
            return False
        return True


@register_mapper('convert_to_uah_by_memo')
class ConvertToEurByMemo:
    """Converts a value found in memo to EUR according to NBU exchange rate."""
    def __init__(self, *args, **kwargs):
        self.prefilter = PreFilterConvertToEurByMemo(args, kwargs)
        self.ex_rate_cache = {}

    def __call__(self, t: YnabTransaction) -> YnabTransaction:
        # TODO: Handle mixed memo

        # Safeguard
        if not self.prefilter(t):
            return t

        m = self.prefilter.RE.match(t.detail.memo.replace(',', ''))

        # Load ex rates cache if needed
        if t.detail.var_date not in self.ex_rate_cache:
            self.ex_rate_cache = init_rates_cache(Currency.EUR, t.detail.var_date, datetime.now().date())
        memo_amount = float(m.group(2))
        # Re-format memo
        t.detail.memo = f'€{memo_amount:,.2f}'
        # Convert currency
        converted_amount = memo_amount * self.ex_rate_cache[t.detail.var_date]
        # Present in milliunits format
        t.detail.amount = -int(converted_amount*1000)
        return t



# TODO: register_mapper('currency_convert') — convert amounts between currencies


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


def _build_read_from_source(ctx: PipelineContext, params: dict):
    """Build a read step that creates transaction streams from bank sources."""
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
    """Build a read step that creates transaction streams from a YNAB budget."""
    time_range_cfg = params.get('time_range')

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        tr = resolve_time_range(time_range_cfg) if time_range_cfg else None
        for budget_key, accounts in params['from_budget'].items():
            budget = ctx.budgets[budget_key]
            wrapper = ynab_api.SingleBudgetYnabApiWrapper(
                ynab_api.YnabApiWrapper(budget.token), budget.budget_name)
            for acc in accounts:
                yield from wrapper.get_transactions_by_account(acc, tr.start.date())

    return step


def _build_read(ctx: PipelineContext, params: dict):
    """Build a read step that creates transaction stream."""
    if 'from_source' in params:
        return _build_read_from_source(ctx, params)
    elif 'from_budget' in params:
        return _build_read_from_budget(ctx, params)
    else:
        raise ValueError(f'Cannot recognize read params: {list(params.keys())}')


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


def _build_map(ctx: PipelineContext, params):
    """Build a map step from registry."""
    if isinstance(params, str):
        name, kwargs = params, {}
    else:
        kwargs = dict(params)
        name = kwargs.pop('type')

    kwargs['ctx'] = ctx
    map_fn = _MAPPERS[name](**kwargs)

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        return map(map_fn, stream)

    return step


def _build_write(ctx: PipelineContext, params: dict):
    """Build a write step. Creates new or updates existing transactions."""
    budget_key = params['to']
    budget = ctx.budgets[budget_key]
    timestamp_file = params.get('timestamp')

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        wrapper = ynab_api.SingleBudgetYnabApiWrapper(
            ynab_api.YnabApiWrapper(budget.token), budget.budget_name)
        transactions = list(stream)

        to_create = [t for t in transactions if not t.detail.id]  # empty or None
        to_update = [t for t in transactions if t.detail.id]

        if to_create:
            print(f'Creating {len(to_create)} transactions in "{budget.budget_name}"...')
            result = wrapper.create_transactions(to_create)
            if result:
                print(f'-- Created: {len(result.transaction_ids)}')

        if to_update:
            print(f'Updating {len(to_update)} transactions in "{budget.budget_name}"...')
            result = wrapper.update_transactions(to_update)
            if result:
                print(f'-- Updated: {len(result.transaction_ids)}')

        if not to_create and not to_update:
            print('-- Nothing to import')

        if timestamp_file:
            with open(timestamp_file, 'w') as f:
                f.write(datetime.now().astimezone().isoformat())
            print(f'Saved timestamp to {timestamp_file}')

        return iter(transactions)

    return step
