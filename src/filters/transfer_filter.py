from model.transaction import YnabTransaction

class TransferFilter:
    """Filter object that prevents duplication of transfers between two YNAB accounts.
    If a pair of transactions that describe a single transfer appear in a single set, 
    YNAB will register both of them independently. This filter object will remove one in each pair.
    """

    def __init__(self):
        self.transfer_statements = []

    def __make_transfer_id(t: YnabTransaction, forward: bool):
        src = t.account.iban
        dst = t.transfer_account.iban
        amount = t.amount
        return forward and f'{src}_{dst}_{amount}' or f'{dst}_{src}_{-amount}'

    def __call__(self, t: YnabTransaction):
        if t.transfer_account:
            try:
                self.transfer_statements.remove(TransferFilter.__make_transfer_id(t, False))
                return False
            except ValueError:
                self.transfer_statements.append(TransferFilter.__make_transfer_id(t, True))
        return True
