from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Iterable
from typing import Any
import re
from datetime import datetime

@dataclass
class TimeRange:
    start: datetime
    end: datetime

@dataclass
class BankAccountConfiguration:
    enabled: bool
    ynab_name: str
    iban: str
    transfer_payee: list[re.Pattern]

class BankApiName(StrEnum):
    MONO = 'monobank'
    PUMB = 'pumb'
    SENSE = 'sensebank'
    ABANK = 'abank'
    PB = 'privatbank'
    UKRSIB = 'ukrsibbank'
    TRACKING = 'tracking'

    @classmethod
    def from_str(cls, value_str):
        for member in cls:
            if member.value == value_str:
                return member
        raise ValueError(f"{value_str} is not a valid value for {cls.__name__}")

@dataclass
class BankApiConfiguration:
    name: BankApiName
    token: str
    n_retries: int
    remove_cancelled_statements: bool
    accounts: list[BankAccountConfiguration]

@dataclass
class YnabConfiguration:
    token: str
    budget_name: str

@dataclass
class YnabCategory:
    name: str
    group: str

class RegexDict:
    """Dict-like collection whose keys are regular expressions 
    """

    def __init__(self, iterable: Iterable[tuple[re.Pattern, Any]]):
        self.__elements = list(iterable)

    def __repr__(self):
        return self.__elements.__repr__()

    def get(self, key, default=None, condition=lambda _: True):
        """Find an element whose regex pattern-key matches a given key
        """
        return next((value for pattern,value in self.__elements
            if pattern.match(key) and condition(value)), default)

@dataclass
class YnabCategoryMappings:
    by_mcc: dict[int, YnabCategory]
    by_payee: RegexDict # of YnabCategory

@dataclass
class StatementFieldMappings:
    account_by_transfer_payee: RegexDict
    category: YnabCategoryMappings
    payee: RegexDict # of payee aliases

@dataclass
class Configuration:
    merge_transfer_statements: bool
    remember_last_import_timestamp: bool
    time_range: TimeRange
    apis: list[BankApiConfiguration]
    ynab: YnabConfiguration
    mappings: StatementFieldMappings

    def __init__(self, import_settings_json, categories_json, payees_json, timestamp_json=None):
        self.merge_transfer_statements = import_settings_json['merge_transfer_statements']
        self.remember_last_import_timestamp = import_settings_json['remember_last_import_timestamp']
        self.apis = []

        self.time_range = self.__time_range(
            timestamp_json=self.remember_last_import_timestamp and timestamp_json,
            **import_settings_json['bank']['time_range'])

        for api_name, api_conf_list in import_settings_json['bank']['api'].items():
            for api_conf_json in api_conf_list:
                self.apis.append(BankApiConfiguration(
                    name=BankApiName.from_str(api_name),
                    token=api_conf_json['token'],
                    n_retries=import_settings_json['bank']['n_retries'],
                    remove_cancelled_statements=import_settings_json['remove_cancelled_statements'],
                    accounts=[BankAccountConfiguration(
                            **(a | {
                                'transfer_payee': self.__pattern(*a.get('transfer_payee', []), "Transfer : " + re.escape(a['ynab_name'])),
                                'iban': a.get('iban')}))
                        for a in api_conf_json['accounts']]))

        self.mappings = StatementFieldMappings(
            account_by_transfer_payee=RegexDict((a.transfer_payee, a) for c in self.apis for a in c.accounts if a.transfer_payee),
            category=YnabCategoryMappings(
                by_mcc={ mcc: YnabCategory(**c['ynab_category']) for c in categories_json for mcc in c['criterias'].get('mcc', []) },
                by_payee=RegexDict((self.__pattern(*c["criterias"].get("payee", [])), YnabCategory(**c['ynab_category']))
                    for c in categories_json if len(c["criterias"].get("payee", [])))),
            payee=RegexDict((self.__pattern(*regexes), alias) for alias,regexes in payees_json.items() if len(regexes)))
            
        self.ynab = YnabConfiguration(**import_settings_json['ynab'])

    @property
    def timestamp(self):
        return {'last_import': datetime.now(tz=self.time_range.start.tzinfo).isoformat()}

    @staticmethod
    def __time_range(timestamp_json, start, end):
        last_import = timestamp_json and datetime.fromisoformat(timestamp_json['last_import'])
        time_range_start = datetime.fromisoformat(start)
        if last_import and last_import > time_range_start:
            time_range_start = last_import
        return TimeRange(
            start=time_range_start,
            end=end and datetime.fromisoformat(end) or datetime.now(tz=time_range_start.tzinfo))

    @staticmethod
    def __pattern(*regex_str_list):
        return re.compile(f'(?:{"|".join(regex_str_list)})') if len(regex_str_list) else None
