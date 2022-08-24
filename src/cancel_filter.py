from collections import defaultdict

class CancelFilter:
    cancel_suffix = 'Скасування. '

    def __init__(self, all_transactions):
        self.cancel_transactions = defaultdict(list)
        for t in all_transactions:
            payee = t['payee_name']
            if payee.startswith(self.cancel_suffix):
                self.cancel_transactions[payee[len(self.cancel_suffix):]].append(t['amount'])

    def __call__(self, transaction):
        payee = transaction['payee_name']
        if payee.startswith(self.cancel_suffix):
            return False
        try:
            self.cancel_transactions[payee].remove(-transaction['amount'])
            return False
        except ValueError:
            return True
