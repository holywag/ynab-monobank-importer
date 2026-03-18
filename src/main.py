#!/usr/bin/env python3

import config
from sources import BankApiSource
from filters.transfer_filter import TransferFilter
import ynab_api
import json, itertools
from datetime import datetime

TIMESTAMP_FILE = './config/timestamp.json'

print('Initialization')

cfg = config.load()

print('Starting import')

ynab = ynab_api.SingleBudgetYnabApiWrapper(ynab_api.YnabApiWrapper(cfg.ynab.token), cfg.ynab.budget_name)

sources = [BankApiSource(api_conf, cfg.mappings, cfg.time_range) for api_conf in cfg.apis]
ynab_trans = list(itertools.chain.from_iterable(src.read() for src in sources))

print(f'Processing {len(ynab_trans)} transactions...')

if cfg.merge_transfer_statements:
    ynab_trans = list(filter(TransferFilter(), ynab_trans))

print(f'Sending {len(ynab_trans)}...')

result = ynab.create_transactions(ynab_trans)

if result:
    print(f'-- Imported: {len(result.transaction_ids)}')
else:
    print('-- Nothing to import')

if cfg.remember_last_import_timestamp:
    timestamp = {'last_import': datetime.now(tz=cfg.time_range.start.tzinfo).isoformat()}
    with open(TIMESTAMP_FILE, 'w') as f:
        json.dump(timestamp, f)
