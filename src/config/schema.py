"""Pydantic models for YAML configuration validation."""

from pydantic import BaseModel, Field
from typing import Literal, Annotated


class AccountConfig(BaseModel):
    enabled: bool = False
    iban: str | None = None
    ynab_name: str = ''  # TODO: move to pipeline/sink config
    transfer_patterns: list[str] = []


class MonobankSourceConfig(BaseModel):
    type: Literal['monobank']
    token: str
    retries: int = 5
    remove_cancelled: bool = True
    accounts: dict[str, AccountConfig]


class FilesystemSourceConfig(BaseModel):
    type: Literal['pumb', 'pumb_credit', 'sensebank', 'abank', 'privatbank', 'ukrsibbank', 'millennium']
    path: str
    accounts: dict[str, AccountConfig]


class TrackingSourceConfig(BaseModel):
    type: Literal['tracking']
    accounts: dict[str, AccountConfig]


SourceConfig = Annotated[
    MonobankSourceConfig | FilesystemSourceConfig | TrackingSourceConfig,
    Field(discriminator='type'),
]


class MappingsRef(BaseModel):
    categories: str  # path to categories YAML
    payees: str      # path to payees YAML
    # transfer patterns are defined per-account in sources


class BudgetConfig(BaseModel):
    token: str
    budget: str
    mappings: MappingsRef


class RootConfig(BaseModel):
    sources: str           # path to sources YAML
    budgets: str           # path to budgets YAML
    pipelines: dict[str, str]  # name → path to pipeline YAML
