from bank_api import BankApi, Transaction, UnknownIban, MissingAccountConfiguration
import model.configuration as conf
from datetime import datetime
from collections.abc import Iterable

class Api(BankApi):
    def __init__(self, configuration: conf.BankApiConfiguration):
        pass

    def request_statements_for_time_range(self, iban: str, start: datetime, end: datetime) -> Iterable[Transaction]:
        return iter([])
