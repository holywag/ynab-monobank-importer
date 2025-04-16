#!/usr/bin/env python3


import model.configuration as conf
import ynab_api
from model.transaction import Transaction, YnabTransaction, YnabTransactionGroup
from filters.transfer_filter import TransferFilter
import json, itertools, os, datetime as dt
import pandas as pd
import requests, re
from dataclasses import dataclass
from enum import StrEnum

RATES_CACHE_FILE='rates_cache.json'

class Currency(StrEnum):
    EUR='eur'

def request_ex_rates(date_start: dt.date, date_stop: dt.date, currency: Currency) -> dict[dt.date, float]:
    fmt = 'https://bank.gov.ua/NBU_Exchange/exchange_site?start={date_start}&end={date_stop}&valcode={currency}&sort=exchangedate&order=desc&json'
    url = fmt.format(
        date_start=f'{date_start.year}{date_start.month:02}{date_start.day:02}',
        date_stop=f'{date_stop.year}{date_stop.month:02}{date_stop.day:02}',
        currency=currency)
    resp = requests.get(url)
    return {dt.datetime.strptime(i['exchangedate'], '%d.%m.%Y').date(): float(i['rate_per_unit']) for i in resp.json()}

def init_rates_cache(currency: Currency, date_start: dt.date, date_stop: dt.date):
    cache = {}
    try:
        cache = {dt.datetime.strptime(k, '%Y-%m-%d').date(): v \
            for k,v in json.load(open(RATES_CACHE_FILE, 'r')).items()}
        sorted_cache_dates = sorted(cache)
        if date_start in cache and date_stop in cache:
            print(f'Ex rates cache: loaded {len(cache)} entries from {sorted_cache_dates[0]} to {sorted_cache_dates[-1]}')
            return cache
    except Exception as e:
        # print(e)
        pass

    if cache:
        if date_start in cache:
            date_start = sorted_cache_dates[-1]
        if date_stop in cache:
            date_stop = sorted_cache_dates[0]
    
    print(f'Ex rates cache: requesting rates from {date_start} to {date_stop}')
    cache |= request_ex_rates(date_start, date_stop, currency)
    json.dump({str(k): v for k,v in cache.items()}, open(RATES_CACHE_FILE, 'w'), default=str)
    print(f'Ex rates cache: stored {len(cache)} entries')
    return cache

def main():
    cfg = conf.Configuration(
        json.load(open('config/import_settings.json')),
        json.load(open('config/categories.json')),
        json.load(open('config/payees.json')))

    # parse ynab database   
    df = pd.read_csv('reg.csv')

    # Transfers are represented in ynab by two transactions - outflow from source and inflows to destination
    # We need to remove one in each pair to prevent duplication of transfers during import
    df.drop(df[(df.Inflow != 0) & df.Payee.str.match('^Transfer :', na=False)].index, inplace=True)

    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y').dt.date

    tracking_accounts = [a.ynab_name for api in cfg.apis for a in api.accounts if api.name == conf.BankApiName.TRACKING]
    is_transfer_from_tracking = df.Account.isin(tracking_accounts) & df.Payee.str.match('^Transfer :', na=False)
    # Inflow is either a regular inflows or transfer from a tracking account
    is_inflow = (df.Inflow != 0) | is_transfer_from_tracking

    # Get budget inflows with rates
    inflows = df.loc[is_inflow, ('Date', 'Inflow', 'Outflow')].iloc[::-1].copy(deep=True).reset_index(drop=True)
    inflow_dates = inflows['Date'].unique()
    rates = init_rates_cache(Currency.EUR, inflow_dates[0], inflow_dates[-1])
    inflows['Rate'] = inflows['Date'].map(rates)
    inflows['Amount'] = inflows[['Inflow', 'Outflow']].max(axis=1)

    def apply_row_reverse(cond, subset, func):
        df.loc[cond, subset] = df.loc[cond, subset].iloc[::-1].apply(func, axis=1).iloc[::-1]

    # Convert inflows amount based on rate table
    def convert_inflow(row: pd.Series):
        row.Inflow /= rates[row.Date]
        return row

    apply_row_reverse(df.Inflow != 0, ('Date', 'Inflow'), convert_inflow)

    # Convert transfers from tracking accounts amount based on rate table
    def convert_transfer_from_tracking(row: pd.Series):
        row.Outflow /= rates[row.Date]
        return row

    apply_row_reverse(is_transfer_from_tracking, ('Date', 'Outflow'), convert_transfer_from_tracking)

    # Convert transaction amount based on inflows rows
    def convert_outflow():
        inflow_idx = 0

        def __do_convert(outflow, cur_inflow, cur_inflow_idx, is_transfer_within_budget):
            nonlocal inflow_idx

            rate = inflows.at[cur_inflow_idx, 'Rate']

            if outflow > cur_inflow: 
                to_convert = (cur_inflow or outflow)
                next_inflow_idx = min([inflows.index[-1], cur_inflow_idx+1])
                return to_convert / rate + __do_convert(
                    outflow - to_convert, inflows.iloc[next_inflow_idx].Amount, next_inflow_idx, is_transfer_within_budget)
            else:
                if not is_transfer_within_budget:
                    inflows.at[cur_inflow_idx, 'Amount'] -= outflow
                    inflow_idx = cur_inflow_idx
                return outflow / rate

        def __do_convert_outflow(row: pd.Series):
            row.Outflow = __do_convert(
                row.Outflow,
                inflows.iloc[inflow_idx].Amount,
                inflow_idx,
                re.match(f'Transfer : (?!{"|".join(tracking_accounts)})', str(row.Payee)))
            return row

        return __do_convert_outflow

    # Convert budget outflows and transfers within budget
    apply_row_reverse((df.Outflow != 0) & ~is_transfer_from_tracking, ('Date', 'Payee', 'Outflow'), convert_outflow())

    # Convert ynab database to YnabTransaction
    def convert_to_ynab(row: pd.Series, trans: list[YnabTransaction|YnabTransactionGroup]):
        t = YnabTransaction(
            account=next(iter(a for api in cfg.apis for a in api.accounts if a.ynab_name == row.Account)),
            time=dt.datetime.combine(row.Date, dt.time.min),
            amount=int((row.Inflow or -row.Outflow) * 100),
            payee='', # Assign later
            transfer_account=cfg.mappings.account_by_transfer_payee.get(row.Payee),
            category = conf.YnabCategory(name=row.Category, group=row['Category Group']),
            comment=row.Memo
        )

        if split_memo := re.match(r'^Split \((\d+)/\d+\) (.*)', str(row.Memo)):
            t.comment = split_memo[2]
            if split_memo[1] == '1':
                t = YnabTransactionGroup.from_YnabTransaction(t)
                trans.append(t)
            else:
                trans[-1].amount += t.amount
                trans[-1].subtransactions.append(t)
        else:
            trans.append(t)

        if row.Payee != trans[-1].payee:
            t.payee = row.Payee


    trans = []
    string_columns = df.select_dtypes(include='object').columns
    df[string_columns] = df[string_columns].fillna('')
    df[df.Date > (dt.datetime.now().date() - dt.timedelta(days=365*5+1))].apply(convert_to_ynab, args=(trans,), axis=1)

    print(f'Importing transactions: {len(trans)}')

    api = ynab_api.SingleBudgetYnabApiWrapper(ynab_api.YnabApiWrapper(cfg.ynab.token), cfg.ynab.budget_name)
    for i in range(0, len(trans), 1000):
        print(f'Import chunk #{i // 1000}')
        # FIXME: Handle error and print failing transactions
        result = api.create_transactions(trans[i:i+1000])
        print(f'Imported {len(result.transaction_ids)} transactions')

    # Now go to the budget and fix screwed balances by adding "Starting Balance" transactions

if __name__ == '__main__':
    main()
