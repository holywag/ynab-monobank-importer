#!/usr/bin/env python3

import ynab
from monobank import Monobank
import json, argparse
from datetime import datetime
from category_mappings import CategoryMappings

parser = argparse.ArgumentParser()
parser.add_argument('monobank_token', help='monobank API token')
parser.add_argument('iban', help='IBAN of source monobank account')
parser.add_argument('ynab_token', help='YNAB API token')
parser.add_argument('ynab_budget_name', help='name of YNAB budget')
parser.add_argument('ynab_account_id', help='ID of target YNAB account')
parser.add_argument('category_mappings', help='path to a file containing category mappings')
args = parser.parse_args()

monobank = Monobank(args.monobank_token)

mono_account_id = monobank.request_account_id(args.iban)
statements = monobank.request_statements_for_last_n_days(mono_account_id, 1)

if len(statements) == 0:
    print('No statements received from monobank')
    exit()

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
categories_response = categories_api.get_categories(budget_id)
category_groups = { g.name: {c.name: c.id for c in g.categories} for g in categories_response.data.category_groups }

mappings = CategoryMappings(json.load(open(args.category_mappings)))

def get_category_id(category_group_name, category_name):
    category_ids = category_groups.get(category_group_name)
    return category_ids and category_ids.get(category_name)

def stmt_to_transaction(s):
    payee = mappings.get_payee(s['mcc'], s['description']) or s['description']
    category = mappings.get_category(s['mcc'], s['description'])
    category_id = category and get_category_id(category.group, category.name)
    print(f'{payee} {category and (category.group + " " + category.name)} {category_id}')
    return ynab.SaveTransaction(
        account_id=args.ynab_account_id,
        date=datetime.fromtimestamp(int(s['time'])).date(),
        amount=s['amount']*10,
        payee_name=payee,
        category_id=category_id,
        memo=not category_id and f'mcc: {s["mcc"]}' or None)

trans_api = ynab.TransactionsApi(ynab_client)
api_response = trans_api.bulk_create_transactions(
    budget_id, ynab.BulkTransactions(list(map(stmt_to_transaction, statements))))
print(api_response)
