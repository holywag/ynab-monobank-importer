from collections import namedtuple

BankStatement = namedtuple('BankStatement',
    'account id time amount mcc payee description transfer_account category')

class MonobankStatementParser:
    """Convert statement received from Monobank API to BankStatement object
    for further processing.
    Each statement is categorised using field_settings in the following order:
    - by transfer payee
    - by payee name mapping
    - by mcc mapping
    """

    def __init__(self, account, field_settings):
        self.account = account
        self.field_settings = field_settings

    def __call__(self, s):
        mcc = s['mcc']
        description = s['description']
        return BankStatement(
            account=self.account,
            id=s['id'],
            time=s['time'],
            amount=s['amount'],
            mcc=mcc,
            description=description,
            payee=self.field_settings.payee_aliases_by_payee_regex.get(description, description),
            transfer_account=self.field_settings.accounts_by_transfer_payee_regex.get(description, condition=lambda a: a.iban != self.account.iban),
            category=self.field_settings.categories_by_payee_regex.get(description, self.field_settings.categories_by_mcc.get(mcc)))
