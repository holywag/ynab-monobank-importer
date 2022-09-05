from collections import namedtuple
import re

MonobankImportSettings = namedtuple('MonobankImportSettings', 'token n_days n_retries')
YnabImportSettings = namedtuple('YnabImportSettings', 'token budget_name import_id_prefix')
Account = namedtuple('Account', 'enabled ynab_name iban transfer_payee')
StatementFieldSettings = namedtuple('StatementFieldSettings', 'accounts_by_transfer_payee_regex categories_by_mcc categories_by_payee_regex payee_aliases_by_payee_regex')
YnabCategory = namedtuple('YnabCategory', 'group name')
RegexItem = namedtuple('RegexItem', 'regex_key value')

class RegexList(list):
    def get(self, key, default=None):
        return next((r.value for r in self if r.regex_key.match(key)), default)

class Configuration:
    def __init__(self, import_settings_json, accounts_json, categories_json, payees_json):
        self.monobank = MonobankImportSettings(**import_settings_json['monobank'])
        self.ynab = YnabImportSettings(**import_settings_json['ynab'])
        self.accounts = [Account(**a) for a in accounts_json]
        self.statement_field_settings = StatementFieldSettings(
            accounts_by_transfer_payee_regex=
                RegexList([Configuration.__re_item(a.transfer_payee, a) for a in self.accounts if len(a.transfer_payee)]),
            categories_by_payee_regex=
                RegexList([Configuration.__re_item(c["criterias"].get("payee", []), YnabCategory(**c['ynab_category'])) 
                    for c in categories_json if len(c["criterias"].get("payee", []))]),
            payee_aliases_by_payee_regex=
                RegexList([Configuration.__re_item(regexes, alias) for alias,regexes in payees_json.items() if len(regexes)]),
            categories_by_mcc=
                { mcc: YnabCategory(**c['ynab_category']) for c in categories_json for mcc in c['criterias'].get('mcc', []) })

    def __re_item(regex_list, value):
        return RegexItem(re.compile(f'(?:{"|".join(regex_list)})'), value)
