from bank_api import BankApi, Transaction, UnknownIban, MissingAccountConfiguration
from model.configuration import BankApiConfiguration
import tabula
import pandas as pd
import re
from pathlib import Path
from datetime import datetime
from collections.abc import Iterable

# todo: support other currencies?
# todo: use original column names for better integrity
# todo: determine the real timezone

class Api(BankApi):
    def __init__(self, conf: BankApiConfiguration):
        self.conf = conf
        self.accounts = { a.iban: a for a in conf.accounts if a.iban }

    def request_statements_for_time_range(self, iban: str, start: datetime, end: datetime) -> Iterable[Transaction]:
        account = self.accounts.get(iban)
        if not account:
            raise UnknownIban(self.conf.name, iban)
        rglob = list((Path(self.conf.token) / account.iban).rglob('*.pdf'))
        if len(rglob) == 0:
            return []
        df = pd.concat(self.__parse_pdf(f) for f in rglob)
        df.drop_duplicates(['date', 'amount_uah'], keep='last', inplace=True)
        df = df.apply(axis=1, result_type='reduce', func=lambda row: Transaction(
            time=datetime.strptime(row.date, '%Y-%m-%d\r%H:%M:%S').astimezone(start.tzinfo),
            amount=int(float(re.match(r'(-?\d+\.\d{2})(?: UAH)', row.amount_uah).group(1)) * (100 if row.type == 'Надходження' else -100)),
            description=' '.join(re.split(r'\s+', row.description)),
            account=account))
        return filter(lambda t: start <= t.time <= end, df)

    def __parse_pdf(self, filepath: Path) -> pd.DataFrame:
        df = tabula.read_pdf(filepath, pages='all', lattice=True, multiple_tables=False)[0]
        df.columns = ['date', 'amount_orig', 'date_posted', 'amount_uah', 'commission', 'card_num', 'description', 'type']
        df.drop(df.tail(4).index, inplace=True) # Drop summary
        # Merge rows that may be occasionally splitted between pages
        return df.groupby((~df['amount_uah'].isna()).cumsum(), as_index=False).agg(
            lambda i: '\r'.join(map(str, filter(lambda j: not pd.isna(j), i))))
