from datetime import datetime

YnabTransaction = dict

class YnabTransactionConverter:
    """Convert MonobankStatement object to the format of YNAB transaction
    """
    def __init__(self, ynab_api):
        self.ynab_api = ynab_api

    def __call__(self, monobank_statement):
        category_id, payee_id = None, None
        if monobank_statement.category:
            category_id = self.ynab_api.get_category_id_by_name(
                monobank_statement.category.group, monobank_statement.category.name)
        if monobank_statement.transfer_account:
            payee_id = self.ynab_api.get_transfer_payee_id_by_account_name(
                monobank_statement.transfer_account.ynab_name)
        return YnabTransaction({
            'account_id': self.ynab_api.get_account_id_by_name(monobank_statement.account.ynab_name),
            'date': datetime.fromtimestamp(int(monobank_statement.time)).date(),
            'amount': monobank_statement.amount*10,
            'payee_name': monobank_statement.payee,
            'payee_id': payee_id,
            'category_id': category_id,
            'memo': not category_id and not payee_id and f'mcc: {monobank_statement.mcc} description: {monobank_statement.description}' or None })
