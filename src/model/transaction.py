import model.configuration as conf
from datetime import datetime
from dataclasses import dataclass, asdict, KW_ONLY

@dataclass
class Transaction:
    account: conf.BankAccountConfiguration
    time: datetime
    amount: int
    description: str
    _: KW_ONLY
    comment: str = None
    mcc: int = None
    id: str = None

@dataclass()
class YnabTransaction(Transaction):
    payee: str
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
        self.payee = mappings.payee.get(self.description) or self.description
        self.transfer_account = mappings.account_by_transfer_payee.get(
            self.description, condition=lambda a: a.iban != self.account.iban)
        self.category = mappings.category.by_payee.get(self.description)
        if not self.category and self.mcc:
            self.category = mappings.category.by_mcc.get(self.mcc)
