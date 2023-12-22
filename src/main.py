#!/usr/bin/env python3

import model.configuration as conf
from model.transaction import YnabTransaction
from filters.transfer_filter import TransferFilter
from ynab_api_wrapper import YnabApiWrapper, SingleBudgetYnabApiWrapper
import bank_api.factory as bank_api_factory
import json, itertools, os
from functools import partial

TIMESTAMP_FILE = './config/timestamp.json'

print('Initialization')

cfg = conf.Configuration(
    json.load(open('config/import_settings.json')),
    json.load(open('config/categories.json')),
    json.load(open('config/payees.json')),
    os.path.isfile(TIMESTAMP_FILE) and json.load(open(TIMESTAMP_FILE)))

print('Starting import')

ynab_api = SingleBudgetYnabApiWrapper(YnabApiWrapper(cfg.ynab.token), cfg.ynab.budget_name)

statement_chain = []

for api_conf in cfg.apis:
    api = bank_api_factory.create(api_conf)
    for account in api_conf.accounts:
        if not account.enabled:
            continue
        print(f'{account.iban} --> {account.ynab_name}')
        trans = api.request_statements_for_time_range(
            account.iban, cfg.time_range.start, cfg.time_range.end)
        if trans:
            statement_chain = itertools.chain(statement_chain, trans)

print('Processing...')

# Categorize transactions by converting them to YnabTransaction
ynab_trans = map(partial(YnabTransaction, cfg.mappings), statement_chain)

if cfg.merge_transfer_statements:
    ynab_trans = filter(TransferFilter(), ynab_trans)

print(f'Sending...')

bulk = ynab_api.bulk_create_transactions(ynab_trans)

if bulk:
    print(f'-- Duplicate: {len(bulk.duplicate_import_ids)}')
    print(f'-- Imported: {len(bulk.transaction_ids)}')
else:
    print(f'-- Nothing to import')

if cfg.remember_last_import_timestamp:
    json.dump(cfg.timestamp, open(TIMESTAMP_FILE, 'w'))
