from .fs import FilesystemBankApiEngine
from model.configuration import AbankOptions
import tabula
import pandas as pd
from pathlib import Path
from datetime import datetime

class Engine(FilesystemBankApiEngine):
    def __init__(self, options: AbankOptions | None = None):
        self.options = options or AbankOptions()

    @property
    def glob_pattern(self) -> str:
        return '*.pdf'
    
    def parse_document(self, f: Path) -> pd.DataFrame:
        df = pd.concat(tabula.read_pdf(f, pages='all', lattice=True))
        df.rename(inplace=True, columns={
            'Дата і час\rоперації': 'date', 
            'Деталі операції': 'description', 
            'МСС': 'mcc', 
            'Сума у валюті\rкарти (UAH)': 'amount_uah',
            'Валюта': 'currency',
            'Сума у валюті\rоперації': 'amount_orig',
            })
        amount_cols = ['amount_uah', 'amount_orig']
        df[amount_cols] = df[amount_cols].apply(
            lambda s: s.str.replace(' ', '', regex=False)
                        .str.replace(',', '.', regex=False)
                        .astype(float))
        return df

    def parse_row(self, row: pd.Series) -> dict:
        amount = row.amount_orig if self.options.orig_amount else row.amount_uah
        return {
            'time': datetime.strptime(row.date, '%d.%m.%Y\r%H:%M'),
            'amount': int(amount * 100),
            'description': row.description,
            'mcc': row.mcc
        } | ({} if self.options.orig_amount else {
            'comment': f'{abs(row.amount_orig):,.2f}'
        })
