import argparse

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('monobank_token', help='monobank API token')
    parser.add_argument('iban', help='IBAN of source monobank account')
    parser.add_argument('ynab_token', help='YNAB API token')
    parser.add_argument('ynab_budget_id', help='ID of target YNAB budget')
    parser.add_argument('ynab_account_id', help='ID of target YNAB account')
    parser.add_argument('category_mappings', help='path to a file containing category mappings')
    return parser.parse_args()
