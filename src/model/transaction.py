"""Pure transaction data classes — no conversion logic."""

import model.configuration as conf
from datetime import datetime
from dataclasses import dataclass, KW_ONLY


@dataclass
class Transaction:
    account: conf.BankAccountConfiguration
    time: datetime
    amount: int
    _: KW_ONLY
    description: str = ''
    comment: str = None
    mcc: int = None
    id: str = None


@dataclass
class YnabTransaction(Transaction):
    payee: str = None
    transfer_account: conf.BankAccountConfiguration = None
    category: conf.YnabCategory = None


@dataclass
class YnabTransactionGroup(YnabTransaction):
    subtransactions: list[YnabTransaction] = None

    @classmethod
    def from_YnabTransaction(cls, t: YnabTransaction):
        return cls(**{field: getattr(t, field) for field in t.__dataclass_fields__}, subtransactions=[t])
