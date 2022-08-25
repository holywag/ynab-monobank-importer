from collections import defaultdict

class CancelFilter:
    """Callable object that acts as a filter function that filters out
    cancelled transactions as well as the respective cancel statements.
    Cancel transaction has a payee field that start with a special prefix.
    """

    cancel_prefix = 'Скасування. '

    def __init__(self, all_transactions):
        cancel, other = [], defaultdict(list)
        for t in all_transactions:
            payee = t['description']
            if payee.startswith(self.cancel_prefix):
                cancel.append(t)
            else:
                other[f'{payee}_{t["amount"]}'].append(t)
        self.skip_transactions = set()
        for t in cancel:
            try:
                cancel_payee = t['description']
                original_transaction = other[f'{cancel_payee[len(self.cancel_prefix):]}_{-t["amount"]}'].pop()
                self.skip_transactions.update({t['id'], original_transaction['id']})
            except IndexError:
                # Ok, caught in case if the corresponding expense statement is not found in the original transaction set
                pass

    def __call__(self, transaction):
        return not transaction['id'] in self.skip_transactions
