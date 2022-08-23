#!/usr/bin/env python3

import ynab
from monobank import Monobank
import argparse, json
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('monobank_token', help='monobank API token')
parser.add_argument('iban', help='IBAN of source monobank account')
parser.add_argument('ynab_token', help='YNAB API token')
parser.add_argument('ynab_budget_id', help='ID of target YNAB budget')
parser.add_argument('ynab_account_id', help='ID of target YNAB account')
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

categories_api = ynab.CategoriesApi(ynab_client)
categories_response = categories_api.get_categories(args.ynab_budget_id)
category_groups = { g.name: {c.name: c.id for c in g.categories} for g in categories_response.data.category_groups }

category_mappings = json.load(open('mappings/category.json'))

def get_payee_and_category(s):
    payee_name = None
    category_group_name = None
    category_name = None
    default = None

    mapping_group = category_mappings.get(str(s['mcc']))

    if mapping_group:
        default = mapping_group['default']
        mapping = mapping_group.get(s['description'])
        if mapping:
            payee_name = mapping.get('payee_name')
            category_group_name = mapping.get('category_group')
            category_name = mapping.get('category_name')

    if not payee_name:
        payee_name = default and default.get('payee_name') or s['description']
    if not category_group_name:
        category_group_name = default and default.get('category_group')
    if category_group_name and not category_name:
        category_name = default and default.get('category_name')
    category_ids = category_groups.get(category_group_name)

    return (payee_name, category_ids and category_ids.get(category_name))


def stmt_to_transaction(s):
    (payee_name, category_id) = get_payee_and_category(s)
    print(f'{payee_name}: {category_id}')
    return ynab.SaveTransaction(
        account_id=args.ynab_account_id,
        date=datetime.fromtimestamp(int(s['time'])).date(),
        amount=s['amount']*10,
        payee_name=payee_name,
        category_id=category_id)

trans_api = ynab.TransactionsApi(ynab_client)
api_response = trans_api.bulk_create_transactions(
    args.ynab_budget_id, ynab.BulkTransactions(list(map(stmt_to_transaction, statements))))
print(api_response)
