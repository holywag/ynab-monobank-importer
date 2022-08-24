import ynab

 
class YnabApiWrapper:
    def __init__(self, token):
        configuration = ynab.Configuration()
        configuration.api_key['Authorization'] = token
        configuration.api_key_prefix['Authorization'] = 'Bearer'

        self.__client = ynab.ApiClient(configuration)

        self.__budgets = None
        self.__accounts = {}
        self.__categories = {}

    @property
    def budgets(self):
        if self.__budgets is None:
            budgets_api = ynab.BudgetsApi(self.__client)
            budgets_response = budgets_api.get_budgets()
            self.__budgets = { b.name: b.id for b in budgets_response.data.budgets }
        return self.__budgets

    def get_budget_id_by_name(self, name):
        return self.budgets.get(name)

    def get_category_id_by_name(self, budget_id, category_group_name, category_name):
        categories = self.__categories.get(budget_id)
        if categories is None:
            categories_api = ynab.CategoriesApi(self.__client)
            categories = { g.name: {c.name: c.id for c in g.categories} for g in categories_api.get_categories(budget_id).data.category_groups }
            self.__categories[budget_id] = categories
        
        category_group = categories.get(category_group_name)
        return category_group and category_group.get(category_name)

    def get_account_id_by_name(self, budget_id, account_name):
        accounts = self.__accounts.get(budget_id)
        if accounts is None:
            accounts_api = ynab.AccountsApi(self.__client)
            accounts = { a.name: a.id for a in accounts_api.get_accounts(budget_id).data.accounts }
            self.__accounts[budget_id] = accounts
        return accounts.get(account_name)

    def bulk_create_transactions(self, budget_id, transactions):
        transactions_api = ynab.TransactionsApi(self.__client)
        response = transactions_api.bulk_create_transactions(
            budget_id, ynab.BulkTransactions(list(map(lambda t: ynab.SaveTransaction(**t), transactions))))
        return response.data.bulk
        

