#!/usr/bin/env python3

from monobank import Monobank
from category_mappings import CategoryMappings
from ynab_api_wrapper import YnabApiWrapper 
from collections import namedtuple
from datetime import datetime
import json, argparse

parser = argparse.ArgumentParser()
parser.add_argument('monobank_token', help='monobank API token')
parser.add_argument('ynab_token', help='YNAB API token')
parser.add_argument('ynab_budget_name', help='name of YNAB budget')
parser.add_argument('account_mappings', help='path to a file containing account mappings')
parser.add_argument('category_mappings', help='path to a file containing category mappings')
args = parser.parse_args()

category_mappings = CategoryMappings(json.load(open(args.category_mappings)))
account_mappings = json.load(open(args.account_mappings))

monobank = Monobank(args.monobank_token)
ynab = YnabApiWrapper(args.ynab_token)

budget_id = ynab.get_budget_id_by_name(args.ynab_budget_name)

if not budget_id:
    print('Budget with the name specified is not found')
    exit(1)

Transaction = namedtuple("Transaction", "account_id date amount payee_name category_id memo")

def stmt_to_transaction(ynab_account_id):
    def impl(stmt):
        payee = category_mappings.get_payee(stmt['mcc'], stmt['description']) or stmt['description']
        category = category_mappings.get_category(stmt['mcc'], stmt['description'])
        category_id = category and ynab.get_category_id_by_name(budget_id, category.group, category.name)
        return {
            'account_id': ynab_account_id,
            'date': datetime.fromtimestamp(int(stmt['time'])).date(),
            'amount': stmt['amount']*10,
            'payee_name': payee,
            'category_id' :category_id,
            'memo': not category_id and f'mcc: {stmt["mcc"]}' or None }
    return impl

for iban,ynab_account_name in account_mappings.items():
    ynab_account_id = ynab.get_account_id_by_name(budget_id, ynab_account_name)
    if not ynab_account_id:
        print(f'The account with the name {ynab_account_name} is not found. Skipping.')
        continue
    mono_account_id = monobank.request_account_id(iban)
    statements = monobank.request_statements_for_last_n_days(mono_account_id, 1)
    if len(statements) == 0:
        print(f'No statements in {ynab_account_name} for this period. Skipping.')
        continue
    bulk = ynab.bulk_create_transactions(
        budget_id, list(map(stmt_to_transaction(ynab_account_id), statements)))
    print(f'Imported {len(bulk.transaction_ids)} transactions out of {len(statements)} bank statements to {ynab_account_name}')
