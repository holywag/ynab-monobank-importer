from bank_api.fs import FilesystemBankApiEngine
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
        df.rename(inplace=True, columns={'Дата\rоперації': 'date', 'Деталі операції': 'description', 'Сума у\rвалюті\rкартки': 'amount'})
        df['amount'] = df['amount'].str.replace(' ', '').str.replace(',', '.').astype(float)
        return df

    def parse_row(self, row: pd.Series) -> dict:
        return {
            'time': datetime.strptime(row.date, '%d.%m.%Y\r%H:%M'),
            'amount': int(row.amount * 100),
            'description': row.description,
        }
