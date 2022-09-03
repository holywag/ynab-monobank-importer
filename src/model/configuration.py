from collections import namedtuple
import re

ImportSettings = namedtuple('ImportSettings', 'monobank_token ynab_token n_days budget_name')
Account = namedtuple('Account', 'enabled ynab_name iban transfer_payee')
YnabCategory = namedtuple('YnabCategory', 'group name')
RegexItem = namedtuple('RegexItem', 'regex_key value')

class RegexList(list):
    def get(self, key, default=None):
        return next((r.value for r in self if r.regex_key.match(key)), default)

class Configuration:
    def __init__(self, import_settings_json, accounts_json, categories_json, payees_json):
        self.import_settings = ImportSettings(**import_settings_json)
        self.accounts = [Account(**a) for a in accounts_json]
        self.accounts_by_transfer_payee_regex = \
            RegexList([Configuration.__re_item(a.transfer_payee, a) for a in self.accounts if len(a.transfer_payee)])
        self.categories_by_mcc = { mcc: YnabCategory(**c['ynab_category']) 
            for c in categories_json for mcc in c['criterias'].get('mcc', []) }
        self.categories_by_payee_regex = \
            RegexList([Configuration.__re_item(c["criterias"].get("payee", []), YnabCategory(**c['ynab_category'])) 
                for c in categories_json if len(c["criterias"].get("payee", []))])
        self.payee_aliases_by_payee_regex = RegexList([Configuration.__re_item(regexes, alias)
            for alias,regexes in payees_json.items() if len(regexes)])

    def __re_item(regex_list, value):
        return RegexItem(re.compile(f'(?:{"|".join(regex_list)})'), value)
