#!/usr/bin/env python3

import model.configuration as conf
from model.transaction import YnabTransaction
from filters.transfer_filter import TransferFilter
from ynab_api_wrapper import YnabApiWrapper, SingleBudgetYnabApiWrapper
from bank_api import BankApi
from mono import Api as MonoApi
from pumb import Api as PumbApi
import json, itertools, os
from functools import partial

TIMESTAMP_FILE = './config/timestamp.json'

def create_api(configuration: conf.BankApiConfiguration) -> BankApi:
    match configuration.name:
        case conf.BankApiName.MONO:
            return MonoApi(configuration)
        case conf.BankApiName.PUMB:
            return PumbApi(configuration)

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
    api = create_api(api_conf)
    for account in api_conf.accounts:
        if not account.enabled:
            continue
        print(f'{account.iban} --> {account.ynab_name}')
        trans = api.request_statements_for_time_range(
            account.iban, cfg.time_range.start, cfg.time_range.end)
        if trans:
            statement_chain = itertools.chain(statement_chain, trans)
        else:
            print(f'No statements fetched for the given period. Skipping.')

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
