"""NBU exchange rate fetching with file-based caching."""

import json
import datetime as dt
from enum import StrEnum

import requests

RATES_CACHE_FILE = 'rates_cache.json'


class Currency(StrEnum):
    EUR = 'eur'


def _request_ex_rates(date_start: dt.date, date_stop: dt.date, currency: Currency) -> dict[dt.date, float]:
    url = (
        f'https://bank.gov.ua/NBU_Exchange/exchange_site'
        f'?start={date_start.year}{date_start.month:02}{date_start.day:02}'
        f'&end={date_stop.year}{date_stop.month:02}{date_stop.day:02}'
        f'&valcode={currency}&sort=exchangedate&order=desc&json'
    )
    resp = requests.get(url)
    return {dt.datetime.strptime(i['exchangedate'], '%d.%m.%Y').date(): float(i['rate_per_unit']) for i in resp.json()}


def init_rates_cache(currency: Currency, date_start: dt.date, date_stop: dt.date):
    cache = {}
    try:
        with open(RATES_CACHE_FILE) as f:
            cache = {dt.datetime.strptime(k, '%Y-%m-%d').date(): v for k, v in json.load(f).items()}
        sorted_cache_dates = sorted(cache)
        if date_start in cache and date_stop in cache:
            print(f'Ex rates cache: loaded {len(cache)} entries from {sorted_cache_dates[0]} to {sorted_cache_dates[-1]}')
            return cache
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    if cache:
        sorted_cache_dates = sorted(cache)
        if date_start in cache:
            date_start = sorted_cache_dates[-1]
        if date_stop in cache:
            date_stop = sorted_cache_dates[0]

    print(f'Ex rates cache: requesting rates from {date_start} to {date_stop}')
    cache |= _request_ex_rates(date_start, date_stop, currency)
    with open(RATES_CACHE_FILE, 'w') as f:
        json.dump({str(k): v for k, v in cache.items()}, f, default=str)
    print(f'Ex rates cache: stored {len(cache)} entries')
    return cache
