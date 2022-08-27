#!/usr/bin/env python3

from monobank import Monobank
from transaction_mappings import TransactionMappings
from account_mappings import AccountMappings
from ynab_api_wrapper import YnabApiWrapper 
from transaction_converter import TransactionConverter
from cancel_filter import CancelFilter
import json, argparse, traceback

parser = argparse.ArgumentParser()
parser.add_argument('monobank_token', help='Monobank API token')
parser.add_argument('ynab_token', help='YNAB API token')
parser.add_argument('ynab_budget_name', help='Name of YNAB budget')
parser.add_argument('account_mappings', help='Path to a file containing account mappings')
parser.add_argument('transaction_mappings', default=None, help='Path to a file containing transaction mappings. If not provided, transactions are imported as is, without any changes.')
args = parser.parse_args()

account_mappings = AccountMappings(json.load(open(args.account_mappings)))
transaction_mappings = TransactionMappings(args.transaction_mappings and json.load(open(args.transaction_mappings)) or {}) 

monobank = Monobank(args.monobank_token)
ynab = YnabApiWrapper(args.ynab_token)

budget_id = ynab.get_budget_id_by_name(args.ynab_budget_name)

if not budget_id:
    print('Budget with the name specified is not found')
    exit(1)

for account in account_mappings:
    if not account.is_import_enabled:
        continue
    print(f'Starting import from {account.iban} to {account.ynab_account_name}')
    try:
        mono_account_id = monobank.request_account_id(account.iban)
        ynab_account_id = ynab.get_account_id_by_name(budget_id, account.ynab_account_name)
        statements = monobank.request_statements_for_last_n_days(mono_account_id, account.import_n_days)
        if len(statements) == 0:
            print(f'No statements fetched for the last {account.import_n_days} days. Skipping.')
            continue
        cancel_filter = CancelFilter(statements)
        bulk = ynab.bulk_create_transactions(budget_id, 
            list(
                map(TransactionConverter(ynab, budget_id, ynab_account_id, transaction_mappings),
                    filter(cancel_filter,
                        statements))))
        print(f'Fetched: {len(statements)}')
        print(f'Cancelled: {len(cancel_filter.skip_transactions)}')
        print(f'Duplicate: {len(bulk.duplicate_import_ids)}')
        print(f'Imported: {len(bulk.transaction_ids)}')
    except Exception:
        print(traceback.format_exc())
        continue
