from model.transaction import Transaction
from abc import ABC, abstractmethod
from datetime import datetime
from collections.abc import Iterable

class UnknownIban(Exception):
    def __init__(self, api_name: str, iban: str):
        super().__init__(f'{api_name}: The IBAN {iban} could not be located')
        self.api_name = api_name
        self.iban = iban

class MissingAccountConfiguration(Exception):
    def __init__(self, api_name: str, iban: str):
        super().__init__(f'{api_name}: Account configuration is missing for IBAN {iban}')
        self.api_name = api_name
        self.iban = iban

class BankApi(ABC):
    """Generic interface for various bank APIs.
    Interface implentation should know how to deal with the corresponding bank API.
    """

    @abstractmethod
    def request_statements_for_time_range(self, iban: str, start: datetime, end: datetime) -> Iterable[Transaction]:
        pass
