from collections import namedtuple

AccountMapping = namedtuple('AccountMapping', 'is_import_enabled iban ynab_account_name import_n_days')

class AccountMappings:
    """Helper class that parses account.json
    """

    def __init__(self, mappings):
        self.mappings = [ AccountMapping(**m) for m in mappings ]

    def __iter__(self):
        return iter(self.mappings)
