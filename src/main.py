#!/usr/bin/env python3

from monobank import Monobank
from ynab_api_wrapper import YnabApiWrapper 
from model.account_mappings import AccountMappings
from model.statement_mappings import StatementMappings
from model.monobank_statement import MonobankStatementParser
from model.ynab_transaction import YnabTransactionConverter
from filters.cancel_filter import CancelFilter
from filters.transfer_filter import TransferFilter
import json, argparse, traceback, itertools, time

parser = argparse.ArgumentParser()
parser.add_argument('monobank_token', help='Monobank API token')
parser.add_argument('ynab_token', help='YNAB API token')
parser.add_argument('ynab_budget_name', help='Name of YNAB budget')
parser.add_argument('account_mappings', help='Path to a file containing account mappings')
parser.add_argument('statement_mappings', default=None, help='Path to a file containing statement field mappings. If not provided, bank statements are imported as is, without any changes.')
args = parser.parse_args()

account_mappings = AccountMappings(json.load(open(args.account_mappings)))
statement_mappings = StatementMappings(args.statement_mappings and json.load(open(args.statement_mappings)) or {}) 

bank = Monobank(args.monobank_token)
ynab = YnabApiWrapper(args.ynab_token)

budget_id = ynab.get_budget_id_by_name(args.ynab_budget_name)

if not budget_id:
    print('Budget with the name specified is not found')
    exit(1)

statement_chain = []
transfer_filter = TransferFilter()

for account in account_mappings:
    if not account.is_import_enabled:
        continue
    print(f'{account.iban} --> {account.ynab_account_name}')
    try:
        bank_account_id = bank.request_account_id(account.iban)
        statements = bank.request_statements_for_last_n_days(bank_account_id, account.import_n_days)
        if len(statements) == 0:
            print(f'No statements fetched for the last {account.import_n_days} days. Skipping.')
            continue
        print(f'-- Fetched: {len(statements)}')
        statement_chain = itertools.chain(statement_chain, 
            map(YnabTransactionConverter(ynab, budget_id),
            filter(transfer_filter,             # Transfer filter - one per session, used for all accounts
            filter(CancelFilter(statements),    # Cancel filter - one per account
            map(MonobankStatementParser(account.ynab_account_name, statement_mappings),
                statements)))))
    except Exception:
        print(traceback.format_exc())
        continue
    # Sleep for 3s to avoid "Too many requests" response from Monobank
    time.sleep(3)

print('Processing...')

transactions = list(statement_chain)

print(f'Sending...')

bulk = ynab.bulk_create_transactions(budget_id, transactions)

print(f'-- Duplicate: {len(bulk.duplicate_import_ids)}')
print(f'-- Imported: {len(bulk.transaction_ids)}')
