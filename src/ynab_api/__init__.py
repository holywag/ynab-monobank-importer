from pprint import pprint as pp
import ynab_openapi as ynab
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
    Account = namedtuple('Account', 'id name transfer_payee_id')
    Category = namedtuple('Category', 'id group_name name')

    def __init__(self, token):
        configuration = ynab.Configuration()
        configuration.access_token = token

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

    def _ensure_accounts(self, budget_id):
        if budget_id not in self.__accounts:
            accounts_api = ynab.AccountsApi(self.__client)
            self.__accounts[budget_id] = {
                a.id: self.Account(id=a.id, name=a.name, transfer_payee_id=a.transfer_payee_id)
                for a in accounts_api.get_accounts(budget_id).data.accounts
            }
        return self.__accounts[budget_id]

    def get_accounts(self, budget_id):
        return self._ensure_accounts(budget_id)

    def get_account_by_id(self, budget_id, account_id):
        """Look up an account by its ID. Returns Account(id, name, transfer_payee_id) or None."""
        return self._ensure_accounts(budget_id).get(account_id)

    def _ensure_categories(self, budget_id):
        if budget_id not in self.__categories:
            categories_api = ynab.CategoriesApi(self.__client)
            cats = {}
            for g in categories_api.get_categories(budget_id).data.category_groups:
                for c in g.categories:
                    cats[c.id] = self.Category(id=c.id, group_name=g.name, name=c.name)
            self.__categories[budget_id] = cats
        return self.__categories[budget_id]

    def get_category_by_id(self, budget_id, category_id):
        """Look up a category by its ID. Returns Category(id, group_name, name) or None."""
        return self._ensure_categories(budget_id).get(category_id)

    def get_category_id_by_name(self, budget_id, category_group_name, category_name):
        for cat in self._ensure_categories(budget_id).values():
            if cat.group_name == category_group_name and cat.name == category_name:
                return cat.id
        return None

    def get_account_by_name(self, budget_id, account_name):
        """Look up an account by name. Returns Account(id, name, transfer_payee_id)."""
        for acc in self._ensure_accounts(budget_id).values():
            if acc.name == account_name:
                return acc
        raise YnabAccountNotFound(account_name)

    def create_transactions(self, budget_id, transactions: Iterable[YnabTransaction]):
        data = [self.__to_new_transaction(t) for t in transactions]
        if not data:
            return None
        transactions_api = ynab.TransactionsApi(self.__client)
        response = transactions_api.create_transaction(
            budget_id, ynab.PostTransactionsWrapper(transactions=data))
        return response.data

    def update_transactions(self, budget_id, transactions: Iterable[YnabTransaction]):
        data = [ynab.SaveTransactionWithIdOrImportId.from_dict(t.detail.to_dict()) for t in transactions]
        if not data:
            return None
        transactions_api = ynab.TransactionsApi(self.__client)
        response = transactions_api.update_transactions(
            budget_id, ynab.PatchTransactionsWrapper(transactions=data))
        # TODO: fix _response_types_map in transactions_api.update_transactions()
        return response.data

    def get_transactions(self, budget_id) -> list[YnabTransaction]:
        transactions_api = ynab.TransactionsApi(self.__client)
        response = transactions_api.get_transactions(budget_id)
        return [YnabTransaction(detail=t) for t in response.data.transactions]

    def get_transactions_by_account(self, budget_id, account_name, since_date) -> list[YnabTransaction]:
        transactions_api = ynab.TransactionsApi(self.__client)
        response = transactions_api.get_transactions_by_account(
            budget_id, self.get_account_by_name(budget_id, account_name).id, since_date)
        return [YnabTransaction(detail=t) for t in response.data.transactions]

    @staticmethod
    def __to_new_transaction(t: YnabTransaction) -> ynab.NewTransaction:
        """Build NewTransaction from detail. All IDs must be pre-resolved."""
        d = t.detail
        return ynab.NewTransaction(
            account_id=d.account_id,
            date=d.var_date,
            amount=d.amount,
            payee_name=(d.payee_name or '')[:50],
            payee_id=d.payee_id,
            category_id=d.category_id,
            memo=d.memo,
        )

class SingleBudgetYnabApiWrapper:
    def __init__(self, ynab_api: YnabApiWrapper, budget_name: str):
        self.ynab_api = ynab_api
        self.budget = ynab_api.get_budget_by_name(budget_name)

    def get_accounts(self):
        return self.ynab_api.get_accounts(self.budget.id)

    def get_account_by_id(self, account_id):
        return self.ynab_api.get_account_by_id(self.budget.id, account_id)

    def get_account_by_name(self, account_name):
        return self.ynab_api.get_account_by_name(self.budget.id, account_name)

    def get_category_by_id(self, category_id):
        return self.ynab_api.get_category_by_id(self.budget.id, category_id)

    def get_category_id_by_name(self, category_group_name, category_name):
        return self.ynab_api.get_category_id_by_name(self.budget.id, category_group_name, category_name)

    def create_transactions(self, transactions: Iterable[YnabTransaction]):
        return self.ynab_api.create_transactions(self.budget.id, transactions)

    def update_transactions(self, transactions: Iterable[YnabTransaction]):
        return self.ynab_api.update_transactions(self.budget.id, transactions)

    def get_transactions(self) -> list[YnabTransaction]:
        return self.ynab_api.get_transactions(self.budget.id)

    def get_transactions_by_account(self, account_name, since_date) -> list[YnabTransaction]:
        return self.ynab_api.get_transactions_by_account(self.budget.id, account_name, since_date)
