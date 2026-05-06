"""Pipeline step implementations and registry.

Steps are registered by name and instantiated from YAML config.
Each step is a callable: Iterable[YnabTransaction] -> Iterable[YnabTransaction].

Registered classes implement `filter(t) -> bool` and/or `map(t) -> YnabTransaction`.
"""

from pprint import pprint as pp
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

_REGISTRY: dict[str, type] = {}


def register_method(name):
    """Register a pipeline method class by name. The class should implement
    `filter(self, t) -> bool` and/or `map(self, t) -> YnabTransaction`."""
    def decorator(cls):
        _REGISTRY[name] = cls
        return cls
    return decorator


# --- Built-in methods ---

@register_method('deduplicate_transfers')
class DeduplicateTransfers:
    """Removes duplicate transfer transactions between YNAB accounts."""
    def __init__(self, **kwargs):
        self._filter = TransferFilter()

    def filter(self, t: YnabTransaction) -> bool:
        return self._filter(t)


@register_method('payee')
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

    def map(self, t: YnabTransaction) -> YnabTransaction:
        payee_name = t.detail.payee_name or ''
        mapped = self._payee_map.get(payee_name)
        if mapped:
            t.detail.payee_name = mapped
        return t


@register_method('categorize')
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
        budget_cfg = ctx.budgets[budget]
        self._ynab = ynab_api.SingleBudgetYnabApiWrapper(
            ynab_api.YnabApiWrapper(budget_cfg.token), budget_cfg.budget_name)

    def map(self, t: YnabTransaction) -> YnabTransaction:
        if not t.detail.category_id:
            payee_name = t.detail.payee_name or ''
            mcc = t.bank_transaction.mcc if t.bank_transaction else None
            cat = self._by_payee.get(payee_name) or (self._by_mcc.get(mcc) if mcc else None)
            if cat:
                t.detail.category_id = self._ynab.get_category_id_by_name(cat['group'], cat['name'])
        return t


@register_method('change_date')
class ChangeDateMapper:
    """Alters transaction date."""
    def __init__(self, year=None, **kwargs):
        self.year = year

    def map(self, t: YnabTransaction) -> YnabTransaction:
        if self.year:
            t.detail.var_date = t.detail.var_date.replace(year=self.year)
        return t


@register_method('convert_to_uah_by_memo')
class ConvertToUahByMemo:
    """Filters eligible transactions and converts EUR memo amounts to UAH.
    Also re-formats memo to "<optional description> <euro sign><amount in {0:,.2f}>".
    """

    MEMO_RE = re.compile(
        r'^\s*(?:(?P<text_before>[^\d$€()]+?)'                  # text_before
        r'\s*[-( ]*\s*)?'                                       # delim and/or '('
        r'(?P<currency>[€$])?'                                  # currency symbol
        r'(?P<amount>[\d,]+(?:\.\d{1,2})?)'                     # amount
        r'(?:\s*[-) ]\s*(?P<text_after>[^\d€()]+?)?)?\s*$')     # delim and/or ')' and text_after

    def __init__(self, **kwargs):
        self.ex_rate_cache = {}

    def filter(self, t: YnabTransaction) -> bool:
        if t.detail.transfer_account_id:
            return False
        # Skip splits (for now)
        if t.detail.subtransactions:
            return False
        # Skip transactions with any existing amount.
        # Should be 0 to be eligible for conversion.
        if t.detail.amount:
            return False
        # Match memo and skip different currency.
        if m := self.MEMO_RE.match(t.detail.memo or ''):
            return m.group('currency') in (None, '€')
        return False

    def map(self, t: YnabTransaction) -> YnabTransaction:
        if not self.filter(t):
            return t

        m = self.MEMO_RE.match(t.detail.memo or '')

        # Load ex rates cache if needed
        if t.detail.var_date not in self.ex_rate_cache:
            self.ex_rate_cache = init_rates_cache(Currency.EUR, t.detail.var_date, datetime.now().date())
        memo_amount = float(m.group('amount'))
        # Re-format memo
        text_before = m.group('text_before') or m.group('text_after') or ''
        if len(text_before) > 1:
            text_before = text_before[0].capitalize() + text_before[1:]
        t.detail.memo = f'{text_before} €{memo_amount:,.2f}'
        # Convert currency
        converted_amount = memo_amount * self.ex_rate_cache[t.detail.var_date]
        # Present in milliunits format
        t.detail.amount = -int(converted_amount*1000)
        return t


@register_method('currency_convert')
class CurrencyConvert:
    def __init__(self, **kwargs):
        pass

    def filter(self, t: YnabTransaction) -> bool:
        return t.detail.var_date == datetime(year=2015, month=2, day=10).date()

    def map(self, t: YnabTransaction) -> YnabTransaction:
        t.detail.amount = 10001
        return t


# --- Step builders ---

def build_steps(step_dicts: list[dict], ctx: PipelineContext) -> list:
    """Build executable step callables from pipeline YAML config."""
    steps = []
    for step_dict in step_dicts:
        for step_type, params in step_dict.items():
            match step_type:
                case 'read_from':
                    steps.append(_build_read_from(ctx, params))
                case 'filter':
                    steps.append(_build_filter(ctx, params))
                case 'map':
                    steps.append(_build_map(ctx, params))
                case 'write_to':
                    steps.append(_build_write_to(ctx, params))
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


def _create_instance(ctx, params):
    """Create an instance of a registered method from step params."""
    if isinstance(params, str):
        name, kwargs = params, {}
    else:
        kwargs = dict(params)
        name = kwargs.pop('type')
    kwargs['ctx'] = ctx
    return _REGISTRY[name](**kwargs)


def _build_read_from_source(ctx: PipelineContext, params: dict):
    """Build a read_from step that creates transaction streams from bank sources."""
    from_mapping = params['source']
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


def _build_read_from_ynab_api(ctx: PipelineContext, params: dict):
    """Build a read_from step that creates transaction streams from a YNAB budget."""
    time_range_cfg = params.get('time_range')

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        tr = resolve_time_range(time_range_cfg) if time_range_cfg else None
        for budget_key, accounts in params['ynab_api'].items():
            budget = ctx.budgets[budget_key]
            wrapper = ynab_api.SingleBudgetYnabApiWrapper(
                ynab_api.YnabApiWrapper(budget.token), budget.budget_name)
            for acc in accounts:
                yield from wrapper.get_transactions_by_account(acc, tr.start.date())

    return step


def _build_read_from(ctx: PipelineContext, params: dict):
    """Build a read_from_from step that creates transaction stream."""
    if 'source' in params:
        return _build_read_from_source(ctx, params)
    elif 'ynab_api' in params:
        return _build_read_from_ynab_api(ctx, params)
    else:
        raise ValueError(f'Cannot recognize read_from params: {list(params.keys())}')


def _build_filter(ctx, params):
    """Build a filter step from registry."""
    instance = _create_instance(ctx, params)

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        return filter(instance.filter, stream)

    return step


def _build_map(ctx: PipelineContext, params):
    """Build a map step from registry."""
    instance = _create_instance(ctx, params)

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        return map(instance.map, stream)

    return step


def _build_write_to(ctx: PipelineContext, params: dict):
    """Build a write_to step. Creates new or updates existing transactions."""
    budget_key = params['ynab_api']
    budget = ctx.budgets[budget_key]
    timestamp_file = params.get('timestamp')

    def step(stream: Iterable[YnabTransaction]) -> Iterable[YnabTransaction]:
        wrapper = ynab_api.SingleBudgetYnabApiWrapper(
            ynab_api.YnabApiWrapper(budget.token), budget.budget_name)
        transactions = list(stream)

        to_create = [t for t in transactions if not t.detail.id]
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