import model.configuration as conf
from .data_source import BankApi, mono, pumb, abank, sensebank, privatbank, millennium
from .data_source.fs import FilesystemBankApi

def create(c: conf.BankApiConfiguration) -> BankApi:
    match c.name:
        case conf.BankApiName.MONO:
            return mono.Api(c)
        case conf.BankApiName.PUMB_DEBIT:
            return FilesystemBankApi(c, pumb.Engine(credit=False))
        case conf.BankApiName.PUMB_CREDIT:
            return FilesystemBankApi(c, pumb.Engine(credit=True))
        case conf.BankApiName.SENSE:
            return FilesystemBankApi(c, sensebank.Engine())
        case conf.BankApiName.ABANK:
            return FilesystemBankApi(c, abank.Engine())
        case conf.BankApiName.PB:
            return FilesystemBankApi(c, privatbank.Engine())
        case conf.BankApiName.MILLENNIUM:
            return FilesystemBankApi(c, millennium.Engine())
