from collections import defaultdict

class CancelFilter:
    """Callable object that acts as a filter function that filters out
    cancelled statements as well as the respective cancel statements.
    Cancel statement has a payee field that starts with a special prefix.
    """

    cancel_prefix = 'Скасування. '

    def __init__(self, original_statement_set):
        # Need to iterate over all ORIGINAL statements because the only criteria of 
        # identification of cancel statements is the ORIGINAL payee name prefix
        cancel, other = [], defaultdict(list)
        for s in original_statement_set:
            payee_name = s['description']
            if payee_name.startswith(self.cancel_prefix):
                cancel.append(s)
            else:
                other[f'{payee_name}_{s["amount"]}'].append(s)
        self.skip_statements = set()
        for s in cancel:
            try:
                original_transaction = other[f'{s["description"][len(self.cancel_prefix):]}_{-s["amount"]}'].pop()
                self.skip_statements.update({s['id'], original_transaction['id']})
            except IndexError:
                # Ok, caught in case if the corresponding expense statement is not found in the original transaction set
                pass
        print(f'Cancelled: {len(self.skip_statements)}')

    def __call__(self, statement):
        return not statement.id in self.skip_statements
