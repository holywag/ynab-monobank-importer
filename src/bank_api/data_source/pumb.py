from .fs import FilesystemBankApiEngine
import tabula
import pandas as pd
import re
from pathlib import Path
from datetime import datetime

class Engine(FilesystemBankApiEngine):
    @property
    def glob_pattern(self) -> str:
        return '*.pdf'
    
    def parse_document(self, f: Path) -> pd.DataFrame:
        df = tabula.read_pdf(f, pages='all', lattice=True, multiple_tables=False)[0]
        # todo: map from the original column names
        df.columns = ['date', 'amount_orig', 'date_posted', 'amount_uah', 'commission', 'card_num', 'description', 'type']
        df.drop(df.tail(4).index, inplace=True) # Drop summary
        # Merge rows that may be occasionally splitted between pages
        return df.groupby((~df['amount_uah'].isna()).cumsum(), as_index=False).agg(
            lambda i: '\r'.join(map(str, filter(lambda j: not pd.isna(j), i))))
    
    def post_process(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.drop_duplicates(['date', 'amount_uah'], keep='last')
    
    def parse_row(self, row: pd.Series) -> dict:
        return {
            'time': datetime.strptime(row.date, '%Y-%m-%d\r%H:%M:%S'),
            'amount': int(float(re.match(r'(-?\d+\.\d{2})(?: UAH)', row.amount_uah).group(1)) * (100 if row.type == 'Надходження' else -100)),
            'description': ' '.join(re.split(r'\s+', row.description))
        }
