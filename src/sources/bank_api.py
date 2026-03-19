"""BankApiSource — wraps bank API and converts raw Transactions to YnabTransactions."""

import bank_api as bank_api_factory
from .base import YnabTransactionSource
from model.transaction import Transaction, YnabTransaction
from model.configuration import (
    BankApiConfiguration, StatementFieldMappings, TimeRange, YnabAccountRef,
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
        field_mappings: StatementFieldMappings,
        time_range: TimeRange,
        ynab_mapping: dict[str, YnabAccountRef],
        read_accounts: set[str],
    ):
        self.api_conf = api_conf
        self.field_mappings = field_mappings
        self.time_range = time_range
        self.ynab_mapping = ynab_mapping
        self.read_accounts = read_accounts  # set of "source.account" keys to fetch
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
                    # Detect transfer at bank level
                    t.transfer_account = self.field_mappings.account_by_transfer_payee.get(
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
            payee=self.field_mappings.payee.get(t.description) or t.description,
            category=(
                self.field_mappings.category.by_payee.get(t.description)
                or self.field_mappings.category.by_mcc.get(t.mcc)
            ),
            ynab_account=ynab_account,
            ynab_transfer_account=ynab_transfer,
        )
