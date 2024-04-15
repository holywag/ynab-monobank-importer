from .fs import FilesystemBankApiEngine
import tabula
import pandas as pd
from pathlib import Path
from datetime import datetime

class Engine(FilesystemBankApiEngine):
    @property
    def glob_pattern(self) -> str:
        return '*.pdf'
    
    def parse_document(self, f: Path) -> pd.DataFrame:
        df = pd.concat(tabula.read_pdf(f, pages='all', lattice=True))
        df.rename(inplace=True, columns={'Дата і час\rоперації': 'date', 'Деталі операції': 'description', 'МСС': 'mcc', 'Сума у валюті\rкарти (UAH)': 'amount_uah'})
        df['amount_uah'] = df['amount_uah'].str.replace(' ', '').str.replace(',', '.').astype(float)
        return df

    def parse_row(self, row: pd.Series) -> dict:
        return {
            'time': datetime.strptime(row.date, '%d.%m.%Y\r%H:%M'),
            'amount': int(row.amount_uah * 100),
            'description': ('Transfer: ' if row.mcc in (6010,4829) and row.description == 'Монобанк' else '') + row.description,
            'mcc': row.mcc
        }
