import model.configuration as conf
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class Transaction:
    id: str
    time: datetime
    amount: float
    mcc: int
    payee: str
    description: str
    account: conf.BankAccountConfiguration

@dataclass
class YnabTransaction(Transaction):
    payee_alias: str
    transfer_account: conf.BankAccountConfiguration
    category: conf.YnabCategory

    def __init__(self, mappings: conf.StatementFieldMappings, src: Transaction):
        """
        Init by extending the original Transaction object with additional fields.
        Each statement is categorized using StatementFieldMappings in the following order:
        - by transfer payee: treat as a transfer between YNAB accounts
        - by payee->category mapping
        - by mcc->category mapping
        """
        super().__init__(**{field: getattr(src, field) for field in src.__dataclass_fields__})
        self.payee_alias = mappings.payee.get(self.payee) or self.payee,
        self.transfer_account = mappings.account_by_transfer_payee.get(self.payee, condition=lambda a: a.iban != self.account.iban)
        self.category = mappings.category.by_payee.get(self.payee, mappings.category.by_mcc.get(self.mcc))
