#!/usr/bin/env python3

from monobank import MonobankApi, ApiClient
from ynab_api_wrapper import YnabApiWrapper, SingleBudgetYnabApiWrapper
from model.configuration import Configuration
from model.monobank_statement import MonobankStatementParser
from model.ynab_transaction import YnabTransactionConverter
from filters.cancel_filter import CancelFilter
from filters.transfer_filter import TransferFilter
import json, itertools, os

TIMESTAMP_FILE = './.timestamp'

print('Initialization')

cfg = Configuration(
    json.load(open('configuration/import_settings.json')),
    json.load(open('configuration/accounts.json')),
    json.load(open('configuration/categories.json')),
    json.load(open('configuration/payees.json')),
    os.path.isfile(TIMESTAMP_FILE) and json.load(open(TIMESTAMP_FILE)))

print('Starting import')

bank_api = MonobankApi(ApiClient(cfg.bank.token, cfg.bank.n_retries))
ynab_api = SingleBudgetYnabApiWrapper(YnabApiWrapper(cfg.ynab.token), cfg.ynab.budget_name)

statement_chain = []

for account in cfg.accounts:
    if not account.enabled:
        continue
    print(f'{account.iban} --> {account.ynab_name}')
    bank_account_id = bank_api.request_account_id(account.iban)
    raw_statements = bank_api.request_statements_for_time_range(
        bank_account_id, cfg.bank.time_range.start, cfg.bank.time_range.end)
    if len(raw_statements) == 0:
        print(f'No statements fetched for the given period. Skipping.')
        continue
    print(f'-- Fetched: {len(raw_statements)}')
    bank_statements = list(map(MonobankStatementParser(account, cfg.statement_field_settings), raw_statements))
    if cfg.remove_cancelled_statements:
        bank_statements = filter(CancelFilter(bank_statements), bank_statements)
    statement_chain = itertools.chain(statement_chain, bank_statements)

print('Processing...')

if cfg.merge_transfer_statements:
    statement_chain = filter(TransferFilter(), statement_chain)

transactions = list(map(YnabTransactionConverter(ynab_api), statement_chain))

print(f'Sending...')

bulk = ynab_api.bulk_create_transactions(transactions)

print(f'-- Duplicate: {len(bulk.duplicate_import_ids)}')
print(f'-- Imported: {len(bulk.transaction_ids)}')

json.dump(cfg.timestamp, open(TIMESTAMP_FILE, 'w'))
