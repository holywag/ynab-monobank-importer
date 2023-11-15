from .cancel_filter import CancelFilter
from bank_api import BankApi, Transaction, UnknownIban, MissingAccountConfiguration
from model.configuration import BankApiConfiguration
from monobank import MonobankApi, ApiClient
from datetime import datetime
from collections.abc import Iterable

class Api(BankApi):
    def __init__(self, conf: BankApiConfiguration):
        self.conf = conf
        self.mono_api = MonobankApi(ApiClient(conf.token, conf.n_retries))
        self.accounts = { a.iban: a for a in conf.accounts if a.iban }
        self.__account_id_by_iban = { a['iban']: a['id']
            for a in self.mono_api.request_client_info()['accounts'] }

    def request_statements_for_time_range(self, iban: str, start: datetime, end: datetime) -> Iterable[Transaction]:
        account_id = self.__account_id_by_iban.get(iban)
        if not account_id:
            raise UnknownIban(self.conf.name, iban)
        account = self.accounts.get(iban)
        if not account:
            raise MissingAccountConfiguration(self.conf.name, iban)
        raw_statements = self.mono_api.request_statements_for_time_range(account_id, start, end)
        if self.conf.remove_cancelled_statements:
            raw_statements = filter(CancelFilter(raw_statements), raw_statements)
        return map(lambda s: Transaction(
            account=self.accounts[iban],
            id=s['id'],
            time=datetime.fromtimestamp(int(s['time'])),
            amount=s['amount'],
            mcc=int(s['mcc']),
            description=s['description'],
            payee=s['description']), raw_statements)
