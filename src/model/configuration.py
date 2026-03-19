"""Domain data classes for configuration and pipeline context."""

from dataclasses import dataclass, field
from enum import StrEnum
from collections.abc import Iterable
from typing import Any
import re


@dataclass
class TimeRange:
    start: 'datetime'
    end: 'datetime'


@dataclass
class BankAccountConfiguration:
    enabled: bool
    ynab_name: str  # TODO: move to pipeline/sink config
    iban: str | None
    transfer_payee: re.Pattern | None


class BankApiName(StrEnum):
    MONO = 'monobank'
    PUMB_DEBIT = 'pumb'
    PUMB_CREDIT = 'pumb_credit'
    SENSE = 'sensebank'
    ABANK = 'abank'
    PB = 'privatbank'
    UKRSIB = 'ukrsibbank'
    MILLENNIUM = 'millennium'
    TRACKING = 'tracking'


@dataclass
class BankApiConfiguration:
    name: BankApiName
    token: str
    n_retries: int
    remove_cancelled_statements: bool
    accounts: list[BankAccountConfiguration]


@dataclass
class YnabCategory:
    name: str
    group: str


class RegexDict:
    """Dict-like collection whose keys are regular expressions."""

    def __init__(self, iterable: Iterable[tuple[re.Pattern, Any]]):
        self.__elements = list(iterable)

    def __repr__(self):
        return self.__elements.__repr__()

    def get(self, key, default=None, condition=lambda _: True):
        """Find an element whose regex pattern-key matches a given key."""
        return next((value for pattern, value in self.__elements
            if pattern.match(key) and condition(value)), default)


@dataclass
class YnabCategoryMappings:
    by_mcc: dict[int, YnabCategory]
    by_payee: RegexDict  # of YnabCategory


@dataclass
class StatementFieldMappings:
    account_by_transfer_payee: RegexDict
    category: YnabCategoryMappings
    payee: RegexDict  # of payee aliases


@dataclass
class ResolvedBudget:
    """A YNAB budget with resolved mappings, ready for pipeline use."""
    token: str
    budget_name: str
    mappings: StatementFieldMappings


@dataclass
class PipelineContext:
    """Holds all resolved config data available to pipeline steps."""
    accounts: dict[str, BankAccountConfiguration]
    source_configs: dict[str, BankApiConfiguration]
    budgets: dict[str, ResolvedBudget]
    pipeline_paths: dict[str, str] = field(default_factory=dict)
