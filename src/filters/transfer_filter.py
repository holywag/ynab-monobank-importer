class TransferFilter:
    """Filter object that prevents duplication of transfers between two YNAB accounts.
    If a pair of transactions that describe a single transfer appear in a single set, 
    YNAB will register both of them independently. This filter object will remove one in each pair.
    """

    def __init__(self):
        self.transfer_statements = []

    def __make_transfer_id(statement, forward):
        src = statement.account.iban
        dst = statement.transfer_account.iban
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
