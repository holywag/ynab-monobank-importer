"""Transaction data classes."""

import model.configuration as conf
from datetime import datetime
from dataclasses import dataclass, KW_ONLY
from ynab import TransactionDetail


@dataclass
class BankTransaction:
    """Raw transaction from a bank API. Internal to bank sources."""
    account: conf.BankAccountConfiguration
    time: datetime
    amount: int
    _: KW_ONLY
    description: str = ''
    comment: str = None
    mcc: int = None
    id: str = None
    transfer_account: conf.BankAccountConfiguration = None


@dataclass
class YnabTransaction:
    """Unified transaction type for the pipeline.

    Uses ynab.TransactionDetail as primary data store.
    Optionally references the originating BankTransaction for bank-specific
    fields (mcc, original description) not present in TransactionDetail.
    """
    detail: TransactionDetail
    bank_transaction: BankTransaction = None
