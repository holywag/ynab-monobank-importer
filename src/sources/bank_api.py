"""BankApiSource — wraps bank API and converts BankTransactions to YnabTransactions."""

import bank_api as bank_api_factory
import ynab_openapi as ynab
from .base import YnabTransactionSource
from model.transaction import BankTransaction, YnabTransaction
from model.configuration import (
    BankApiConfiguration, RegexDict, TimeRange, YnabAccountRef,
)
from ynab_api import YnabApiWrapper
from collections.abc import Iterable


class BankApiSource(YnabTransactionSource):
    """Reads from a bank API source and yields YnabTransactions.

    Encapsulates:
    - Bank API creation and statement fetching
    - Transfer detection from bank transaction descriptions
    - Building TransactionDetail with resolved YNAB IDs
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
        self._ynab_wrappers: dict[str, YnabApiWrapper] = {}

    @property
    def api(self):
        if self._api is None:
            self._api = bank_api_factory.create(self.api_conf)
        return self._api

    def _get_ynab_wrapper(self, budget_token: str) -> YnabApiWrapper:
        if budget_token not in self._ynab_wrappers:
            self._ynab_wrappers[budget_token] = YnabApiWrapper(budget_token)
        return self._ynab_wrappers[budget_token]

    def _resolve_ynab_ids(self, ref: YnabAccountRef):
        """Resolve YNAB account_id and transfer_payee_id from account ref."""
        wrapper = self._get_ynab_wrapper(ref.budget.token)
        budget_id = wrapper.get_budget_by_name(ref.budget.budget_name).id
        account_id = wrapper.get_account_id_by_name(budget_id, ref.name)
        transfer_payee_id = wrapper.get_transfer_payee_id_by_account_name(budget_id, ref.name)
        return account_id, transfer_payee_id

    def read(self) -> Iterable[YnabTransaction]:
        for account in self.api_conf.accounts:
            key = f'{account.source_name}.{account.name}'
            if key not in self.read_accounts:
                continue
            ref = self.ynab_mapping[key]
            print(f'{key} --> {ref.budget.budget_name}.{ref.name}')
            raw_trans = self.api.request_statements_for_time_range(
                account.iban, self.time_range.start, self.time_range.end)
            if raw_trans:
                for t in raw_trans:
                    t.transfer_account = self.transfer_patterns.get(
                        t.description, condition=lambda a, acc=account: a is not acc)
                    yield self._to_ynab(t, key)

    def _to_ynab(self, t: BankTransaction, source_account_key: str) -> YnabTransaction:
        """Convert a BankTransaction to YnabTransaction with resolved YNAB IDs."""
        ref = self.ynab_mapping[source_account_key]
        account_id, _ = self._resolve_ynab_ids(ref)

        transfer_account_id = None
        transfer_payee_id = None
        if t.transfer_account:
            transfer_key = f'{t.transfer_account.source_name}.{t.transfer_account.name}'
            transfer_ref = self.ynab_mapping.get(transfer_key)
            if transfer_ref:
                transfer_account_id, transfer_payee_id = self._resolve_ynab_ids(transfer_ref)

        detail = ynab.TransactionDetail(
            id='',
            var_date=t.time.date(),
            amount=t.amount * 10,
            payee_name=t.description,
            memo=t.comment,
            account_id=account_id,
            account_name=ref.name,
            payee_id=transfer_payee_id,
            transfer_account_id=transfer_account_id,
            cleared='uncleared',
            approved=False,
            deleted=False,
            subtransactions=[],
        )

        return YnabTransaction(detail=detail, bank_transaction=t)
