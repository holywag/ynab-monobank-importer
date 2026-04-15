from .cancel_filter import CancelFilter
from .. import BankApi, BankTransaction, UnknownIban, MissingAccountConfiguration
from model.configuration import BankApiConfiguration
from monobank import MonobankApi, ApiClient
from datetime import datetime, timedelta
from collections.abc import Iterable

class Api(BankApi):
    def __init__(self, conf: BankApiConfiguration):
        self.conf = conf
        self.mono_api = MonobankApi(ApiClient(conf.token, conf.n_retries))
        self.accounts = { a.iban: a for a in conf.accounts if a.iban }
        self.__account_id_by_iban = { a['iban']: a['id']
            for a in self.mono_api.request_client_info()['accounts'] }

    def request_statements_for_time_range(self, iban: str, start: datetime, end: datetime) -> Iterable[BankTransaction]:
        account_id = self.__account_id_by_iban.get(iban)
        if not account_id:
            raise UnknownIban(self.conf.type, iban)
        account = self.accounts.get(iban)
        if not account:
            raise MissingAccountConfiguration(self.conf.type, iban)
        
        raw_statements = []
        part = start
        # Request by chunks if period is longer than allowed by Monobank API.
        while part < end:
            step = min(end - part, self.mono_api.MAX_PERIOD)
            next_part = part + step
            print(f'Fetching {account.source_name}.{account.name} from {part} to {next_part}')
            raw_statements.extend(
                self.mono_api.request_statements_for_time_range(account_id, part, next_part))
            part = next_part
            
        if self.conf.remove_cancelled_statements:
            raw_statements = filter(CancelFilter(raw_statements), raw_statements)
        return map(lambda s: BankTransaction(
            account=self.accounts[iban],
            id=s['id'],
            time=datetime.fromtimestamp(int(s['time'])),
            amount=s['amount'],
            mcc=int(s['mcc']),
            comment=s.get('comment'),
            description=s['description']
        ), raw_statements)
