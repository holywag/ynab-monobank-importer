from datetime import datetime

class TransactionConverter:
    """Convert Monobank statement to the format of YNAB transaction
    """

    def __init__(self, ynab, budget_id, ynab_account_id, transaction_mappings):
        self.ynab = ynab
        self.budget_id = budget_id
        self.ynab_account_id = ynab_account_id
        self.transaction_mappings = transaction_mappings

    def __call__(self, monobank_statement):
        mcc = monobank_statement['mcc']
        payee = monobank_statement['description']

        category_group = self.transaction_mappings.get_field(mcc, payee, 'category_group')
        category_name = self.transaction_mappings.get_field(mcc, payee, 'category_name')
        category_id = category_group and category_name and self.ynab.get_category_id_by_name(self.budget_id, category_group, category_name)
        
        transfer_account = self.transaction_mappings.get_field(mcc, payee, 'transfer_account')
        payee_id = transfer_account and self.ynab.get_transfer_payee_id_by_account_name(self.budget_id, transfer_account)
        
        payee_name = self.transaction_mappings.get_field(mcc, payee, 'payee', payee)

        return {
            'account_id': self.ynab_account_id,
            'date': datetime.fromtimestamp(int(monobank_statement['time'])).date(),
            'amount': monobank_statement['amount']*10,
            'payee_name': payee_name,
            'category_id': category_id,
            'memo': not category_id and not payee_id and f'mcc: {mcc}' or None,
            'payee_id': payee_id }
