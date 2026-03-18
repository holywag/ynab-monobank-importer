#!/usr/bin/env python3

import config
from model.transaction import YnabTransaction
from filters.transfer_filter import TransferFilter
import bank_api, ynab_api
import json, itertools
from datetime import datetime
from functools import partial

TIMESTAMP_FILE = './config/timestamp.json'

print('Initialization')

cfg = config.load()

print('Starting import')

ynab = ynab_api.SingleBudgetYnabApiWrapper(ynab_api.YnabApiWrapper(cfg.ynab.token), cfg.ynab.budget_name)

statement_chain = []

for api_conf in cfg.apis:
    if not sum(a.enabled for a in api_conf.accounts):
        continue
    api = bank_api.create(api_conf)
    for account in api_conf.accounts:
        if not account.enabled:
            continue
        print(f'{account.iban} --> {account.ynab_name}')
        trans = api.request_statements_for_time_range(
            account.iban, cfg.time_range.start, cfg.time_range.end)
        if trans:
            statement_chain = itertools.chain(statement_chain, trans)

print('Processing...')

# TODO: Move from_Transaction logic out of model into source/adapter layer
ynab_trans = map(partial(YnabTransaction.from_Transaction, cfg.mappings), statement_chain)

if cfg.merge_transfer_statements:
    ynab_trans = filter(TransferFilter(), ynab_trans)

print('Sending...')

result = ynab.create_transactions(ynab_trans)

if result:
    print(f'-- Imported: {len(result.transaction_ids)}')
else:
    print('-- Nothing to import')

if cfg.remember_last_import_timestamp:
    timestamp = {'last_import': datetime.now(tz=cfg.time_range.start.tzinfo).isoformat()}
    with open(TIMESTAMP_FILE, 'w') as f:
        json.dump(timestamp, f)
