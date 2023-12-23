import ynab
from model.transaction import YnabTransaction
from collections import namedtuple
from collections.abc import Iterable
from functools import partial

class YnabAccountNotFound(Exception):
    def __init__(self, account_name):
        super().__init__(f'YNAB account with the specified name not found: {account_name}')
        self.account_name = account_name

class YnabBudgetNotFound(Exception):
    def __init__(self, budget_name):
        super().__init__(f'YNAB budget with the specified name not found: {budget_name}')
        self.budget_name = budget_name

class YnabApiWrapper:
    Account = namedtuple('Account', 'id transfer_payee_id')

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
            self.__budgets = budgets_response.data.budgets
        return self.__budgets

    def get_budget_by_name(self, name):
        for b in self.budgets:
            if b.name == name:
                return b
        raise YnabBudgetNotFound(name)

    def get_accounts(self, budget_id):
        accounts = self.__accounts.get(budget_id)
        if accounts is None:
            accounts_api = ynab.AccountsApi(self.__client)
            accounts = { a.name: self.Account(a.id, a.transfer_payee_id)
                for a in accounts_api.get_accounts(budget_id).data.accounts }
            self.__accounts[budget_id] = accounts
        return accounts

    def get_category_id_by_name(self, budget_id, category_group_name, category_name):
        categories = self.__categories.get(budget_id)
        if categories is None:
            categories_api = ynab.CategoriesApi(self.__client)
            categories = { g.name: {c.name: c.id for c in g.categories} for g in categories_api.get_categories(budget_id).data.category_groups }
            self.__categories[budget_id] = categories
        
        category_group = categories.get(category_group_name)
        return category_group and category_group.get(category_name)

    def get_account_id_by_name(self, budget_id, account_name):
        accounts = self.get_accounts(budget_id)
        try:
            return accounts[account_name].id
        except ValueError:
            raise YnabAccountNotFound(account_name)

    def get_transfer_payee_id_by_account_name(self, budget_id, account_name):
        accounts = self.get_accounts(budget_id)
        try:
            return accounts[account_name].transfer_payee_id
        except ValueError:
            raise YnabAccountNotFound(account_name)

    def bulk_create_transactions(self, budget_id, transactions: Iterable[YnabTransaction]):
        bulk_t = list(map(partial(self.__SaveTransaction, budget_id), transactions))
        if len(bulk_t) == 0:
            return None
        transactions_api = ynab.TransactionsApi(self.__client)
        response = transactions_api.bulk_create_transactions(
            budget_id, ynab.BulkTransactions(bulk_t))
        return response.data.bulk

    def get_transactions(self, budget_id):
        transactions_api = ynab.TransactionsApi(self.__client)
        response = transactions_api.get_transactions(budget_id)
        return response.data.transactions

    def __SaveTransaction(self, budget_id: str, t: YnabTransaction):
        category_id, payee_id = None, None
        if t.category:
            category_id = self.get_category_id_by_name(budget_id, t.category.group, t.category.name)
        if t.transfer_account:
            payee_id = self.get_transfer_payee_id_by_account_name(budget_id, t.transfer_account.ynab_name)
        memo = t.comment or ''
        if not category_id and not payee_id:
            memo = f'{memo} {t.description} {t.mcc or ""}'.strip()
        return ynab.SaveTransaction(
            account_id=self.get_account_id_by_name(budget_id, t.account.ynab_name),
            date=t.time.date(),
            amount=t.amount*10,
            payee_name=t.payee[:100],
            payee_id=payee_id,
            category_id=category_id,
            memo=memo or None)

class SingleBudgetYnabApiWrapper:
    def __init__(self, ynab_api, budget_name):
        self.ynab_api = ynab_api
        self.budget = ynab_api.get_budget_by_name(budget_name)

    def get_accounts(self):
        return self.ynab_api.get_accounts(self.budget.id)

    def get_category_id_by_name(self, category_group_name, category_name):
        return self.ynab_api.get_category_id_by_name(self.budget.id, category_group_name, category_name)

    def get_account_id_by_name(self, account_name):
        return self.ynab_api.get_account_id_by_name(self.budget.id, account_name)

    def get_transfer_payee_id_by_account_name(self, account_name):
        return self.ynab_api.get_transfer_payee_id_by_account_name(self.budget.id, account_name)

    def bulk_create_transactions(self, transactions: Iterable[YnabTransaction]):
        return self.ynab_api.bulk_create_transactions(self.budget.id, transactions)

    def get_transactions(self):
        return self.ynab_api.get_transactions(self.budget.id)
