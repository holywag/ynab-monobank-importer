from model.transaction import YnabTransaction

class TransferFilter:
    """Filter object that prevents duplication of transfers between two YNAB accounts.
    If a pair of transactions that describe a single transfer appear in a single set,
    YNAB will register both of them independently. This filter object will remove one in each pair.
    """

    def __init__(self):
        self.transfer_statements = []

    def __make_transfer_id(t: YnabTransaction, forward: bool):
        src = t.detail.account_id
        dst = t.detail.transfer_account_id
        amount = t.detail.amount
        date = str(t.detail.var_date)
        return f'{date}_{src}_{dst}_{amount}' if forward else f'{date}_{dst}_{src}_{-amount}'

    def __call__(self, t: YnabTransaction):
        if t.detail.transfer_account_id:
            try:
                self.transfer_statements.remove(TransferFilter.__make_transfer_id(t, False))
                return False
            except ValueError:
                self.transfer_statements.append(TransferFilter.__make_transfer_id(t, True))
        return True
