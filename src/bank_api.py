from monobank import MonobankApi, ApiClient
from model.configuration import BankImportSettings

class BankApi:
    """Interface wrapper for MonobankApi.
    It knows how deal with MonobankApi interface and provides more generic interface.
    """

    class UnknownIban(Exception):
        def __init__(self, iban):
            super().__init__(f'The following IBAN is not owned by the account: {iban}')
            self.iban = iban

    def __init__(self, token: str, n_retries: int):
        self.mono_api = MonobankApi(ApiClient(token, n_retries))
        self.__account_id_by_iban = \
            {a['iban']: a['id'] for a in self.mono_api.request_client_info()['accounts']}
        self.ibans = self.__account_id_by_iban.keys()

    def request_statements_for_time_range(self, iban, datetime_range_start, datetime_range_end):
        account_id = self.__account_id_by_iban.get(iban)
        if not iban:
            raise UnknownIban(iban)
        return self.mono_api.request_statements_for_time_range(
            account_id, datetime_range_start, datetime_range_end)

class BankAccountApi:
    """A utility class that represents API of a single bank account
    """

    def __init__(self, bank_api: BankApi, iban: str):
        self.bank_api = bank_api
        self.iban = iban
    
    def request_statements_for_time_range(self, datetime_range_start, datetime_range_end):
        return self.bank_api.request_statements_for_time_range(
            self.iban, datetime_range_start, datetime_range_end)

class BankAccountApiLocator:
    def __init__(self, bank_settings: BankImportSettings):
        self.__known_tokens = set()
        self.__api_by_iban = {}
        self.bank_settings = bank_settings
    
    def get_account_api(self, iban) -> BankAccountApi:
        api = self.__api_by_iban.get(iban)
        if not api:
            for t in set(self.bank_settings.token) - self.__known_tokens:
                bank_api = BankApi(t, self.bank_settings.n_retries)
                self.__known_tokens.add(t)
                for i in bank_api.ibans:
                    account_api = self.__api_by_iban[i] = BankAccountApi(bank_api, i)
                    if i == iban:
                        api = account_api
        return api