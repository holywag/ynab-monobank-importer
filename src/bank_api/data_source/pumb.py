from .fs import FilesystemBankApiEngine
import tabula
import pandas as pd
import re
from pathlib import Path
from datetime import datetime

class Engine(FilesystemBankApiEngine):
    def __init__(self, credit: bool):
        super().__init__()
        self.credit = credit
        if credit:
            self._columns = ['date', 'description', 'type', 'amount_orig', 'amount_uah', 'unused_1']
            self._datefmt = '%d.%m.%Y'
        else:
            self._columns = ['date', 'amount_orig', 'date_posted', 'amount_uah', 'commission', 'card_num', 'description', 'type']
            self._datefmt = '%Y-%m-%d\r%H:%M:%S'

    @property
    def glob_pattern(self) -> str:
        return '*.pdf'

    def parse_document(self, f: Path) -> pd.DataFrame:
        df = tabula.read_pdf(f, pages='all', lattice=True, multiple_tables=False)[0]
        df.columns = self._columns   # todo: map from the original column names instead of forcing
        if self.credit:
            delims = lambda df: df[df.date.isin(['Картка', 'По рахунку'])]
            df = df.iloc[delims(df).index[0]+1:-2]   # Drop header/footer
            df.drop(delims(df).index, inplace=True)  # Drop delims
        else:
            df.drop(df.tail(4).index, inplace=True) # Drop summary
        # Merge rows that may be occasionally splitted between pages
        return df.groupby((~df['amount_uah'].isna()).cumsum(), as_index=False).agg(
            lambda i: '\r'.join(map(str, filter(lambda j: not pd.isna(j), i))))

    def post_process(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.drop_duplicates(['date', 'amount_uah'], keep='last')

    def parse_row(self, row: pd.Series) -> dict:
        amount = float(re.match(r'(-?\d+\.\d{2})(?:UAH)?', row.amount_uah.replace(' ', '')).group(1))
        return {
            'time': datetime.strptime(row.date, self._datefmt),
            'amount':  int(amount * (100 if row.type == 'Надходження' else -100)),
            'description': ' '.join(re.split(r'\s+', row.description))
        }
