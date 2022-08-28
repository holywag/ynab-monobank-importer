from collections import namedtuple

MonobankStatement = namedtuple('MonobankStatement',
    'id time amount mcc payee transfer_account category_group category_name ynab_account_name')

class MonobankStatementParser:
    """Convert statement received from Monobank API to MonobankStatement object
    """

    def __init__(self, ynab_account_name, statement_mappings):
        self.ynab_account_name = ynab_account_name
        self.statement_mappings = statement_mappings

    def __call__(self, s):
        mcc = s['mcc']
        mappings = self.statement_mappings.get(mcc, s['description'])
        return MonobankStatement(
            id=s['id'],
            time=s['time'],
            amount=s['amount'],
            mcc=mcc,
            payee=mappings.payee,
            transfer_account=mappings.transfer_account,
            category_group=mappings.category_group,
            category_name=mappings.category_name,
            ynab_account_name=self.ynab_account_name)
