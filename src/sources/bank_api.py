"""BankApiSource — wraps bank API and converts raw Transactions to YnabTransactions."""

import bank_api as bank_api_factory
from .base import YnabTransactionSource
from model.transaction import Transaction, YnabTransaction
from model.configuration import (
    BankApiConfiguration, StatementFieldMappings, TimeRange,
)
from collections.abc import Iterable


class BankApiSource(YnabTransactionSource):
    """Reads from a bank API source and yields YnabTransactions.

    Encapsulates:
    - Bank API creation and statement fetching
    - Conversion from raw Transaction to YnabTransaction (payee mapping,
      transfer detection, categorization)
    """

    def __init__(
        self,
        api_conf: BankApiConfiguration,
        mappings: StatementFieldMappings,
        time_range: TimeRange,
    ):
        self.api_conf = api_conf
        self.mappings = mappings
        self.time_range = time_range
        self._api = None

    @property
    def api(self):
        if self._api is None:
            self._api = bank_api_factory.create(self.api_conf)
        return self._api

    def read(self) -> Iterable[YnabTransaction]:
        if not any(a.enabled for a in self.api_conf.accounts):
            return

        for account in self.api_conf.accounts:
            if not account.enabled:
                continue
            print(f'{account.iban} --> {account.ynab_name}')
            raw_trans = self.api.request_statements_for_time_range(
                account.iban, self.time_range.start, self.time_range.end)
            if raw_trans:
                yield from (self._to_ynab(t) for t in raw_trans)

    def _to_ynab(self, t: Transaction) -> YnabTransaction:
        """Convert a raw Transaction to YnabTransaction using field mappings.

        Categorization priority:
        1. Transfer detection via transfer_payee patterns
        2. Category by payee regex match
        3. Category by MCC code
        """
        return YnabTransaction(
            **{field: getattr(t, field) for field in t.__dataclass_fields__},
            payee=self.mappings.payee.get(t.description) or t.description,
            transfer_account=self.mappings.account_by_transfer_payee.get(
                t.description, condition=lambda a: a.ynab_name != t.account.ynab_name),
            category=(
                self.mappings.category.by_payee.get(t.description)
                or self.mappings.category.by_mcc.get(t.mcc)
            ),
        )
