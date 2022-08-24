from datetime import datetime

class TransactionConverter:
    """Convert Monobank statement to the format of YNAB transaction
    """

    def __init__(self, ynab, budget_id, ynab_account_id, category_mappings):
        self.ynab = ynab
        self.budget_id = budget_id
        self.ynab_account_id = ynab_account_id
        self.category_mappings = category_mappings

    def __call__(self, monobank_statement):
        mcc = monobank_statement['mcc']
        payee = monobank_statement['description']
        category = self.category_mappings.get_category(mcc, payee)
        payee = self.category_mappings.get_payee(mcc, payee) or payee
        category_id = category and self.ynab.get_category_id_by_name(self.budget_id, category.group, category.name)
        return {
            'account_id': self.ynab_account_id,
            'date': datetime.fromtimestamp(int(monobank_statement['time'])).date(),
            'amount': monobank_statement['amount']*10,
            'payee_name': payee,
            'category_id': category_id,
            'memo': not category_id and f'mcc: {mcc}' or None }
