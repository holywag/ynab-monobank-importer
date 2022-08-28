from collections import namedtuple

class AccountMappings:
    """Helper class that parses account.json
    """

    AccountMapping = namedtuple('AccountMapping', 'is_import_enabled iban ynab_account_name import_n_days')

    def __init__(self, mappings):
        self.mappings = [ self.AccountMapping(**m) for m in mappings ]

    def __iter__(self):
        return iter(self.mappings)
