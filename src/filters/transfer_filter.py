from collections import defaultdict

class TransferFilter:
    """Filter object that prevents duplication of transfers between two YNAB accounts.
    If a pair of transactions that describe a single transfer appear in a single set, 
    YNAB will register both of them independently. This filter object will remove one in each pair.
    A pair is identified by 'amount', 'time' and 'transfer_account' transaction fields.
    """

    def __init__(self):
        self.transfer_statements = []
        self.removed_statements = []

    def __make_transfer_id(statement, forward):
        src = statement.ynab_account_name
        dst = statement.transfer_account
        amount = statement.amount
        return forward and f'{src}_{dst}_{amount}' or f'{dst}_{src}_{-amount}'

    def __call__(self, statement):
        if statement.transfer_account:
            try:
                self.transfer_statements.remove(TransferFilter.__make_transfer_id(statement, False))
                return False
            except ValueError:
                self.transfer_statements.append(TransferFilter.__make_transfer_id(statement, True))
        return True
