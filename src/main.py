#!/usr/bin/env python3

from monobank import MonobankApi, ApiClient
from ynab_api_wrapper import YnabApiWrapper, SingleBudgetYnabApiWrapper
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

bank = MonobankApi(ApiClient(cfg.monobank.token, cfg.monobank.n_retries))
ynab_api = SingleBudgetYnabApiWrapper(YnabApiWrapper(cfg.ynab.token), cfg.ynab.budget_name)

statement_chain = []

for account in cfg.accounts:
    if not account.enabled:
        continue
    print(f'{account.iban} --> {account.ynab_name}')
    bank_account_id = bank.request_account_id(account.iban)
    raw_statements = bank.request_statements_for_last_n_days(bank_account_id, cfg.monobank.n_days)
    if len(raw_statements) == 0:
        print(f'No statements fetched for the last {cfg.monobank.n_days} days. Skipping.')
        continue
    print(f'-- Fetched: {len(raw_statements)}')
    monobank_statements = list(map(MonobankStatementParser(account, cfg.statement_field_settings), raw_statements))
    statement_chain = itertools.chain(statement_chain,
        filter(CancelFilter(monobank_statements), monobank_statements))

print('Processing...')

transactions = list(
    map(YnabTransactionConverter(ynab_api),
    filter(TransferFilter(),
        statement_chain)))

print(f'Sending...')

bulk = ynab_api.bulk_create_transactions(transactions)

print(f'-- Duplicate: {len(bulk.duplicate_import_ids)}')
print(f'-- Imported: {len(bulk.transaction_ids)}')
