"""Pydantic models for YAML configuration validation."""

from pydantic import BaseModel, Field
from typing import Literal, Annotated


class AccountConfig(BaseModel):
    iban: str | None = None
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


class BudgetConfig(BaseModel):
    token: str
    budget: str


class RootConfig(BaseModel):
    sources: str | dict                   # path to YAML or inline dict
    budgets: str | dict[str, BudgetConfig]  # path to YAML or inline dict
    pipelines: dict[str, str]             # name -> path to pipeline YAML
