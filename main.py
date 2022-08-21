import ynab
from monobank import Monobank
import argparse
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('monobank_token', help='monobank API token')
parser.add_argument('iban', help='IBAN of source monobank account')
parser.add_argument('ynab_token', help='YNAB API token')
parser.add_argument('ynab_budget_id', help='id of target YNAB budget')
parser.add_argument('ynab_account_id', help='id of target YNAB account')
args = parser.parse_args()

monobank = Monobank(args.monobank_token)

mono_account_id = monobank.request_account_id(args.iban)
statements = monobank.request_statements_for_last_n_days(mono_account_id, 1)

if len(statements) == 0:
    print('No statements received from monobank')
    exit()

ynab_configuration = ynab.Configuration()
ynab_configuration.api_key['Authorization'] = args.ynab_token
ynab_configuration.api_key_prefix['Authorization'] = 'Bearer'

def stmt_to_transaction(s):
    return ynab.SaveTransaction(
        account_id=args.ynab_account_id,
        date=datetime.fromtimestamp(int(s['time'])).date(),
        amount=s['amount']*10,
        payee_name=s['description'])

ynab_client = ynab.ApiClient(ynab_configuration)
trans_api = ynab.TransactionsApi(ynab_client)
api_response = trans_api.bulk_create_transactions(
    args.ynab_budget_id, ynab.BulkTransactions(list(map(stmt_to_transaction, statements))))
print(api_response)
