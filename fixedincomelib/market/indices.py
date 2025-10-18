import QuantLib as ql
import json
import os

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

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)

            thisDir  = os.path.dirname(__file__)  # e.g., src/market
            jsonPath = os.path.join(thisDir, "index_registry.json")

            with open(jsonPath, "r") as fileHandle:
                dataMap = json.load(fileHandle)

            registryMap = {}
            for indexKey, className in dataMap.items():
                try:
                    qlClass = getattr(ql, className)
                except AttributeError:
                    raise KeyError(f"QuantLib has no attribute '{className}' for key '{indexKey}'")
                registryMap[indexKey] = qlClass

            cls._instance.RegistryMap = registryMap

        return cls._instance

    def get(cls, key, *args):
        isDaily = len(args) == 0
        functor = cls.RegistryMap.get(key)
        if functor is None:
            raise KeyError(f"IndexRegistry: no entry found for '{key}'")

        return functor() if isDaily else functor(ql.Period(args[0]))
    

indexReg = IndexRegistry()