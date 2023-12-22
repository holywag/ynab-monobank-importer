from bank_api.fs import FilesystemBankApiEngine
import pandas as pd
from pathlib import Path
from datetime import datetime

class Engine(FilesystemBankApiEngine):
    @property
    def glob_pattern(self) -> str:
        return '*.csv'
    
    def parse_document(self, f: Path) -> pd.DataFrame:
        df = pd.read_csv(f, skiprows=5, skipfooter=1, encoding='cp1251', engine='python', sep=';', decimal=',')
        df.rename(inplace=True, columns={'Дата і час': 'date', 'Деталі': 'description', 'MCC': "mcc", 'Cума списання': 'credit', 'Cума зарахування': 'debit'})
        return df
    
    def parse_row(self, row: pd.Series) -> dict:
        return {
            'time': datetime.strptime(row.date, '%d.%m.%y %H:%M'),
            'amount': int((row.credit if pd.isna(row.debit) else row.debit) * 100),
            'description': row.description,
            'mcc': row.mcc
        }
