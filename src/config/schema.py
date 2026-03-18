"""Pydantic models for YAML configuration validation."""

from pydantic import BaseModel, Field
from typing import Literal, Annotated


class AccountConfig(BaseModel):
    iban: str | None = None
    ynab_name: str = ''  # TODO: move to pipeline/sink config
    transfer_patterns: list[str] = []


class MonobankSourceConfig(BaseModel):
    type: Literal['monobank']
    token: str
    retries: int = 5
    remove_cancelled: bool = True
    accounts: dict[str, bool]  # account_id → enabled


class FilesystemSourceConfig(BaseModel):
    type: Literal['pumb', 'pumb_credit', 'sensebank', 'abank', 'privatbank', 'ukrsibbank', 'millennium']
    path: str
    accounts: dict[str, bool]  # account_id → enabled


SourceConfig = Annotated[
    MonobankSourceConfig | FilesystemSourceConfig,
    Field(discriminator='type'),
]


class MappingsRef(BaseModel):
    categories: str  # path to categories YAML
    payees: str      # path to payees YAML


class YnabBudgetConfig(BaseModel):
    token: str
    budget: str
    mappings: MappingsRef


class TimeRangeConfig(BaseModel):
    start: str
    end: str | None = None
    use_last_import: bool = False


class PipelineConfig(BaseModel):
    """Temporary pipeline settings. TODO: replace with pipeline file references."""
    merge_transfer_statements: bool = False
    target_budget: str  # references key in ynab section


class CategoryMatchConfig(BaseModel):
    mcc: list[int] = []
    payee: list[str] = []


class CategoryEntryConfig(BaseModel):
    category: dict[str, str]  # {group: ..., name: ...}
    match: CategoryMatchConfig


class RootConfig(BaseModel):
    accounts: dict[str, AccountConfig]
    sources: dict[str, SourceConfig]
    ynab: dict[str, YnabBudgetConfig]
    time_range: TimeRangeConfig
    pipeline: PipelineConfig
