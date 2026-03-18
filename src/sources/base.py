"""YnabTransactionSource — abstract base for all transaction sources."""

from abc import ABC, abstractmethod
from collections.abc import Iterable

from model.transaction import YnabTransaction


class YnabTransactionSource(ABC):
    """Yields YnabTransactions from any origin (bank API, YNAB budget, file, etc.)."""

    @abstractmethod
    def read(self) -> Iterable[YnabTransaction]:
        ...

    # TODO: YnabBudgetSource — read from another YNAB budget
    # TODO: FileSource — read from CSV/JSON backup
