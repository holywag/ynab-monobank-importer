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
    payee: str
    transfer_account: conf.BankAccountConfiguration
    category: conf.YnabCategory

    @classmethod
    def from_Transaction(cls, mappings: conf.StatementFieldMappings, t: Transaction):
        """
        Init by extending the original Transaction object with additional fields.
        Each statement is categorized using StatementFieldMappings in the following order:
        - by transfer payee: treat as a transfer between YNAB accounts
        - by payee->category mapping
        - by mcc->category mapping
        """
        return cls(
            **{field: getattr(t, field) for field in t.__dataclass_fields__},
            payee=mappings.payee.get(t.description) or t.description,
            transfer_account=mappings.account_by_transfer_payee.get(
                t.description, condition=lambda a: a.ynab_name != t.account.ynab_name),
            category = mappings.category.by_payee.get(t.description) or
                mappings.category.by_mcc.get(t.mcc))

@dataclass
class YnabTransactionGroup(YnabTransaction):
    subtransactions: list[YnabTransaction]

    @classmethod
    def from_YnabTransaction(cls, t: YnabTransaction):
        return cls(**{field: getattr(t, field) for field in t.__dataclass_fields__}, subtransactions=[t,])

