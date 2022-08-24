#!/usr/bin/env python3

from monobank import Monobank
from category_mappings import CategoryMappings
from ynab_api_wrapper import YnabApiWrapper 
from transaction_converter import TransactionConverter
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
        budget_id, list(map(TransactionConverter(ynab, budget_id, ynab_account_id, category_mappings), statements)))
    print(f'Imported {len(bulk.transaction_ids)} transactions out of {len(statements)} bank statements to {ynab_account_name}')
