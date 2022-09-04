#!/usr/bin/env python3

from monobank import MonobankApi, ApiClient
from ynab_api_wrapper import YnabApiWrapper 
from model.configuration import Configuration
from model.monobank_statement import MonobankStatementParser
from model.ynab_transaction import YnabTransactionConverter
from filters.cancel_filter import CancelFilter
from filters.transfer_filter import TransferFilter
import json, itertools

print('Initialization')

cfg = Configuration(
    json.load(open('configuration/import_settings.json')),
    json.load(open('configuration/accounts.json')),
    json.load(open('configuration/categories.json')),
    json.load(open('configuration/payees.json')))

print('Starting import')

bank = MonobankApi(ApiClient(cfg.import_settings.monobank_token, 3))
ynab = YnabApiWrapper(cfg.import_settings.ynab_token)

budget_id = ynab.get_budget_id_by_name(cfg.import_settings.budget_name)

if not budget_id:
    raise Exception(f'Budget with the name {cfg.import_settings.budget_name} is not found.')

statement_chain = []
transfer_filter = TransferFilter()

for account in cfg.accounts:
    if not account.enabled:
        continue
    print(f'{account.iban} --> {account.ynab_name}')
    bank_account_id = bank.request_account_id(account.iban)
    raw_statements = bank.request_statements_for_last_n_days(bank_account_id, cfg.import_settings.n_days)
    if len(raw_statements) == 0:
        print(f'No statements fetched for the last {cfg.import_settings.n_days} days. Skipping.')
        continue
    print(f'-- Fetched: {len(raw_statements)}')
    monobank_statements = list(map(MonobankStatementParser(account, cfg), raw_statements))
    statement_chain = itertools.chain(statement_chain, 
        map(YnabTransactionConverter(ynab, budget_id),
        filter(transfer_filter,                     # Transfer filter - one per session, used for all accounts
        filter(CancelFilter(monobank_statements),   # Cancel filter - one per account
            monobank_statements))))

print('Processing...')

transactions = list(statement_chain)

print(f'Sending...')

bulk = ynab.bulk_create_transactions(budget_id, transactions)

print(f'-- Duplicate: {len(bulk.duplicate_import_ids)}')
print(f'-- Imported: {len(bulk.transaction_ids)}')
