#!/usr/bin/env python3

import ynab
from monobank import Monobank
import json, argparse
from datetime import datetime
from category_mappings import CategoryMappings

parser = argparse.ArgumentParser()
parser.add_argument('monobank_token', help='monobank API token')
parser.add_argument('ynab_token', help='YNAB API token')
parser.add_argument('ynab_budget_name', help='name of YNAB budget')
parser.add_argument('account_mappings', help='path to a file containing account mappings')
parser.add_argument('category_mappings', help='path to a file containing category mappings')
args = parser.parse_args()

monobank = Monobank(args.monobank_token)

ynab_configuration = ynab.Configuration()
ynab_configuration.api_key['Authorization'] = args.ynab_token
ynab_configuration.api_key_prefix['Authorization'] = 'Bearer'

ynab_client = ynab.ApiClient(ynab_configuration)

budgets_api = ynab.BudgetsApi(ynab_client)
budgets_response = budgets_api.get_budgets()
budgets = { b.name: b.id for b in budgets_response.data.budgets }

if not args.ynab_budget_name in budgets:
    print('Budget with the name specified is not found')
    exit(1)

budget_id = budgets[args.ynab_budget_name]

categories_api = ynab.CategoriesApi(ynab_client)
category_groups = { g.name: {c.name: c.id for c in g.categories} for g in categories_api.get_categories(budget_id).data.category_groups }

mappings = CategoryMappings(json.load(open(args.category_mappings)))

def get_category_id(category_group_name, category_name):
    category_ids = category_groups.get(category_group_name)
    return category_ids and category_ids.get(category_name)

def stmt_to_transaction(ynab_account_id):
    def impl(stmt):
        payee = mappings.get_payee(stmt['mcc'], stmt['description']) or stmt['description']
        category = mappings.get_category(stmt['mcc'], stmt['description'])
        category_id = category and get_category_id(category.group, category.name)
        return ynab.SaveTransaction(
            account_id=ynab_account_id,
            date=datetime.fromtimestamp(int(stmt['time'])).date(),
            amount=stmt['amount']*10,
            payee_name=payee,
            category_id=category_id,
            memo=not category_id and f'mcc: {stmt["mcc"]}' or None)
    return impl

acc_api = ynab.AccountsApi(ynab_client)
ynab_accounts = { a.name: a.id for a in acc_api.get_accounts(budget_id).data.accounts }

for iban,ynab_acc_name in json.load(open(args.account_mappings)).items():
    if not ynab_acc_name in ynab_accounts:
        print(f'The account with the name {ynab_acc_name} is not found. Skipping.')
        continue
    mono_account_id = monobank.request_account_id(iban)
    statements = monobank.request_statements_for_last_n_days(mono_account_id, 1)
    if len(statements) == 0:
        print(f'No statements in {ynab_acc_name} for this period. Skipping.')
        continue
    trans_api = ynab.TransactionsApi(ynab_client)
    response = trans_api.bulk_create_transactions(
        budget_id, ynab.BulkTransactions(list(map(stmt_to_transaction(ynab_accounts[ynab_acc_name]), statements))))
    print(f'Imported {len(response.data.bulk.transaction_ids)} transactions out of {len(statements)} bank statements to {ynab_acc_name}')
