import QuantLib as ql

class Currency:

    def __init__(self, input : str) -> None:
        self.value_ = None
        if input.upper() == 'USD':
            self.value_ = ql.USDCurrency()
        elif input.upper() == 'CAD':
            self.value_ = ql.CADCurrency()
        elif input.upper() == 'GBP':
            self.value_ = ql.GBPCurrency()
        elif input.upper() == 'EUR':
            self.value_ = ql.EURCurrency()
        elif input.upper() == 'JPY':
            self.value_ = ql.JPYCurrency()
        elif input.upper() == 'AUD':
            self.value_ = ql.AUDCurrency()
        else:
            raise Exception(input + ' is not current supported currency.')

    @property
    def value(self):
        return self.value_

class IndexRegistry(object):
    
    _instance = None

    ### TODO: make it a json/yaml
    THIS_REGISTRY = {
        'USD-LIBOR-BBA' : ql.USDLibor,
        'SOFR-1B' : ql.Sofr,
        'FF-1B' : ql.FedFunds,
        'GBP-LIBOR-BBA' : ql.GBPLibor,
        'SONIA-1B' : ql.Sonia,
        'CAD-LIBOR-BA' : ql.CADLibor,
        'CORRA-1B' : ql.Corra,
        'EURIBOR' : ql.Euribor,
        'EONIA' : ql.Eonia,
        'AUD-LIBOR-BBA' : ql.AUDLibor,
        'AONIA-1B' : ql.Aonia,
        'JPY-LIBOR-BBA' : ql.JPYLibor,
        'TONIA-1B' : ql.Tona
    }

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
            ### TODO: read from a file instead of hard coded map above
            cls._instance.registry = cls.THIS_REGISTRY
        return cls._instance

    def get(cls, key, *args):
        isDaily = len(args) == 0
        functor = cls.registry.get(key)
        return functor() if isDaily else functor(ql.Period(args[0]))