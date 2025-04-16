from .fs import FilesystemBankApiEngine
import tabula
import pandas as pd
import re
from pathlib import Path
from datetime import datetime
import conv


class Engine(FilesystemBankApiEngine):
    """Parser for Extrato Combinado (monthly) reports by Millennium bcp.
    No lattice, as such relies on the exact column positions.
    """

    @property
    def glob_pattern(self) -> str:
        return 'Extrato Combinado 20*.pdf'

    def parse_document(self, f: Path) -> pd.DataFrame:
        # Columns are located at 1.1, 1.51, 4.7, 5.77, 6.95 inches from the left side.
        df = tabula.read_pdf(f, pages='all', lattice=False, multiple_tables=False, 
                             columns=[13.3, 18.3, 57.1, 70.1, 84.4], relative_columns=True,
                             stream=True, guess=False)[0]
        df.columns=['data_lanc', 'data_valor', 'descritivo', 'debito', 'credito', 'saldo']
        # All data is located between SALDO INICIAL and SALDO FINAL.
        df = df.iloc[
            df[df.descritivo == 'SALDO INICIAL'].index.min()+1
            :df[df.descritivo == 'SALDO FINAL'].index.min()]
        # Drop garbage at page breaks.
        df = df.drop(       # 4. Finally drop them.
            sum(            # 3. Concat all ranges into a single sequence.
                map(        # 2. Expand indexes into ranges of indexes of rows between them.
                    lambda r: list(range(r[0], r[1] + 1)), 
                    zip(    # 1. Collect pairs of indexes indicating page breaks.
                        df[df.descritivo == 'A TRANSPORTAR'].index, # Appears before page break.
                        df[df.descritivo == 'TRANSPORTE'].index,    # Appears after page break.
                        strict=True
        )),[]))
        # Fix date columns: convert to datetime, deduce year from file name
        year = re.match(r'Extrato Combinado (\d{4})\d{3}\.pdf', f.name).group(1)
        df[['data_lanc', 'data_valor']] = (
            df[['data_lanc', 'data_valor']]
                .apply(lambda col: pd.to_datetime(col + f'.{year}', format='%m.%d.%Y')))
        return df

    def post_process(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert EUR to UAH. 
        FIXME: Remove this code once budget migration to EUR is done.
        """
        dates = sorted(df.data_lanc.dt.date.unique())
        rates = df.data_lanc.map(conv.init_rates_cache(conv.Currency.EUR, dates[0], dates[-1]))
        converted_values = (df[['debito', 'credito']]
            .apply(lambda col: col.str.replace(' ', '', regex=False))
            .astype(float)
            .fillna(0))
        df[['debito_orig', 'credito_orig']] = converted_values
        df[['debito', 'credito']] = converted_values.multiply(rates, axis=0)
        return df

    def parse_row(self, row: pd.Series) -> dict:
        return {
            'time': row.data_lanc.to_pydatetime(),
            'amount':  int((row.credito or -row.debito) * 100),
            'description': row.descritivo,
            # FIXME: Remove this memo once budget migration to EUR is done.
            'comment': f'€{row.credito_orig or row.debito_orig:,.2f}'
        }
