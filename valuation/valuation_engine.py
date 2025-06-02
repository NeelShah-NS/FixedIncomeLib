from abc import ABCMeta, abstractmethod
from model import (Model)
from product import (Product)

class ValuationEngine(metaclass=ABCMeta):

    epsilon = 1e-4
    def __init__(self, model : Model, valuationParameters : dict, product : Product):
        self.model = model
        self.product = product
        self.valParams = valuationParameters
        self.valueDate = self.model.valueDate
        self.value_ = None

    @abstractmethod
    def calculateValue(self):
        return
    
    # this should be mandatory as well, @abstractmethod
    # TODO
    def calculateRisk(self):
        pass

    # optional
    def parRateOrSpread(self):
        pass

    # optional
    def createCashflowsReport(self):
        pass

    @property
    def value(self):
        return self.value_

    

