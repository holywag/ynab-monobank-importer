import model.configuration as conf
from bank_api import BankApi
from bank_api.fs import FilesystemBankApi
import bank_api.pumb as pumb, bank_api.mono as mono, bank_api.sensebank as sense

def create(c: conf.BankApiConfiguration) -> BankApi:
    match c.name:
        case conf.BankApiName.MONO:
            return mono.Api(c)
        case conf.BankApiName.PUMB:
            return FilesystemBankApi(c, pumb.Engine())
        case conf.BankApiName.SENSE:
            return FilesystemBankApi(c, sense.Engine())
