import model.configuration as conf
from bank_api import BankApi
from bank_api.fs import FilesystemBankApi
import bank_api.pumb as pumb, bank_api.mono as mono, bank_api.sensebank as sense, bank_api.abank as abank, bank_api.privatbank as privatbank

def create(c: conf.BankApiConfiguration) -> BankApi:
    match c.name:
        case conf.BankApiName.MONO:
            return mono.Api(c)
        case conf.BankApiName.PUMB:
            return FilesystemBankApi(c, pumb.Engine())
        case conf.BankApiName.SENSE:
            return FilesystemBankApi(c, sense.Engine())
        case conf.BankApiName.ABANK:
            return FilesystemBankApi(c, abank.Engine())
        case conf.BankApiName.PB:
            return FilesystemBankApi(c, privatbank.Engine())
