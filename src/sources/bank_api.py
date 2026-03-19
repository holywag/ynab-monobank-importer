"""BankApiSource — wraps bank API and converts raw Transactions to YnabTransactions."""

import bank_api as bank_api_factory
from .base import YnabTransactionSource
from model.transaction import Transaction, YnabTransaction
from model.configuration import (
    BankApiConfiguration, RegexDict, TimeRange, YnabAccountRef,
)
from collections.abc import Iterable


class BankApiSource(YnabTransactionSource):
    """Reads from a bank API source and yields YnabTransactions.

    Encapsulates:
    - Bank API creation and statement fetching
    - Transfer detection from bank transaction descriptions
    - Conversion to YnabTransaction with YNAB account refs
    """

    def __init__(
        self,
        api_conf: BankApiConfiguration,
        transfer_patterns: RegexDict,
        time_range: TimeRange,
        ynab_mapping: dict[str, YnabAccountRef],
        read_accounts: set[str],
    ):
        self.api_conf = api_conf
        self.transfer_patterns = transfer_patterns
        self.time_range = time_range
        self.ynab_mapping = ynab_mapping
        self.read_accounts = read_accounts
        self._api = None

    @property
    def api(self):
        if self._api is None:
            self._api = bank_api_factory.create(self.api_conf)
        return self._api

    def read(self) -> Iterable[YnabTransaction]:
        for account in self.api_conf.accounts:
            key = f'{account.source_name}.{account.name}'
            if key not in self.read_accounts:
                continue
            ynab_ref = self.ynab_mapping[key]
            print(f'{key} --> {ynab_ref.budget.budget_name}.{ynab_ref.name}')
            raw_trans = self.api.request_statements_for_time_range(
                account.iban, self.time_range.start, self.time_range.end)
            if raw_trans:
                for t in raw_trans:
                    t.transfer_account = self.transfer_patterns.get(
                        t.description, condition=lambda a, acc=account: a is not acc)
                    yield self._to_ynab(t, ynab_ref)

    def _to_ynab(self, t: Transaction, ynab_account: YnabAccountRef) -> YnabTransaction:
        """Convert a raw Transaction to YnabTransaction."""
        ynab_transfer = None
        if t.transfer_account:
            key = f'{t.transfer_account.source_name}.{t.transfer_account.name}'
            ynab_transfer = self.ynab_mapping.get(key)

        return YnabTransaction(
            **{field: getattr(t, field) for field in t.__dataclass_fields__},
            payee=t.description,
            ynab_account=ynab_account,
            ynab_transfer_account=ynab_transfer,
        )
