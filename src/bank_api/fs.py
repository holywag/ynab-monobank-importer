from bank_api import BankApi, Transaction, UnknownIban
from model.configuration import BankApiConfiguration
from pathlib import Path
import pandas as pd
from datetime import datetime
from collections.abc import Iterable
from abc import ABC, abstractmethod

class FilesystemBankApiEngine(ABC):
    @property
    @abstractmethod
    def glob_pattern(self) -> str:
        pass

    @abstractmethod
    def parse_document(self, f: Path) -> pd.DataFrame:
        pass
    
    @abstractmethod
    def parse_row(self, row: pd.Series) -> dict:
        pass

    def post_process(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

class FilesystemBankApi(BankApi):
    def __init__(self, conf: BankApiConfiguration, engine: FilesystemBankApiEngine):
        self.conf = conf
        self.accounts = { a.iban: a for a in conf.accounts if a.iban }
        self.engine = engine
    
    def request_statements_for_time_range(self, iban: str, start: datetime, end: datetime) -> Iterable[Transaction]:
        account = self.accounts.get(iban)
        if not account:
            raise UnknownIban(self.conf.name, iban)
        rglob = list((Path(self.conf.token) / account.iban).rglob(self.engine.glob_pattern))
        if len(rglob) == 0:
            return []
        df = pd.concat(self.engine.parse_document(f) for f in rglob)
        df = self.engine.post_process(df)
        def parse_row(r: pd.Series) -> Transaction:
            fields = self.engine.parse_row(r)
            # todo: determine the real timezone
            return Transaction(**(fields | { 'account': account, 'time': fields['time'].astimezone(start.tzinfo) }))
        df = df.apply(parse_row, axis=1, result_type='reduce')
        return filter(lambda t: start <= t.time <= end, df)
