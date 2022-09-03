from collections import namedtuple

MonobankStatement = namedtuple('MonobankStatement',
    'account id time amount mcc payee transfer_account category')

class MonobankStatementParser:
    """Convert statement received from Monobank API to MonobankStatement object
    for further processing.
    """

    def __init__(self, account, configuration):
        self.account = account
        self.cfg = configuration

    def __call__(self, s):
        mcc = s['mcc']
        description = s['description']
        return MonobankStatement(
            account=self.account,
            id=s['id'],
            time=s['time'],
            amount=s['amount'],
            mcc=mcc,
            payee=self.cfg.payee_aliases_by_payee_regex.get(description, description),
            transfer_account=self.cfg.accounts_by_transfer_payee_regex.get(description),
            category=self.cfg.categories_by_payee_regex.get(description, self.cfg.categories_by_mcc.get(mcc)))
