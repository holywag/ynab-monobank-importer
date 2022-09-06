from collections import namedtuple
import re
from datetime import datetime

BankImportSettings = namedtuple('BankImportSettings', 'token n_retries time_range')
TimeRangeSettings = namedtuple('TimeRangeSettings', 'start end')
YnabImportSettings = namedtuple('YnabImportSettings', 'token budget_name')
Account = namedtuple('Account', 'enabled ynab_name iban transfer_payee')
StatementFieldSettings = namedtuple('StatementFieldSettings', 
    'accounts_by_transfer_payee_regex categories_by_mcc categories_by_payee_regex payee_aliases_by_payee_regex')
YnabCategory = namedtuple('YnabCategory', 'group name')
RegexItem = namedtuple('RegexItem', 'regex_key value')

class RegexList(list):
    def get(self, key, default=None):
        return next((r.value for r in self if r.regex_key.match(key)), default)

class Configuration:
    def __init__(self, import_settings_json, accounts_json, categories_json, payees_json):
        self.bank = Configuration.__bank_settings(import_settings_json['bank'])
        self.ynab = YnabImportSettings(**import_settings_json['ynab'])
        self.remove_cancelled_statements = import_settings_json['remove_cancelled_statements']
        self.merge_transfer_statements = import_settings_json['merge_transfer_statements']
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

    def __bank_settings(bank_settings_json):
        time_range_json = bank_settings_json['time_range']
        datetime_start = datetime.fromisoformat(time_range_json['start'])
        time_range_end = time_range_json.get('end')
        bank_settings = bank_settings_json | { 'time_range' : TimeRangeSettings(
            start=datetime_start,
            end=time_range_end and datetime.fromisoformat(time_range_end) or datetime.now(tz=datetime_start.tzinfo)) }
        return BankImportSettings(**bank_settings)

    def __re_item(regex_list, value):
        return RegexItem(re.compile(f'(?:{"|".join(regex_list)})'), value)
