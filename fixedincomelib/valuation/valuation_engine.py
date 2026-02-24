from abc import ABCMeta, abstractmethod
from typing import Dict
import numpy as np
from fixedincomelib.model import (Model)
from fixedincomelib.product import (Product)

class ValuationEngine(metaclass=ABCMeta):

    epsilon = 1e-4
    def __init__(self, model : Model, valuationParameters : dict, product : Product):
        self.model = model
        self.product = product
        self.valParams = valuationParameters
        self.valueDate = self.model.valueDate
        self.value_ = None
        self.firstOrderRisk_ = None

    @abstractmethod
    def calculateValue(self):
        return
    
    @abstractmethod
    def calculateFirstOrderRisk(self,
                                gradient=None,
                                scaler: float = 1.0,
                                accumulate: bool = False,
                                ) -> None:
        return

    # optional
    def parRateOrSpread(self):
        pass

    # optional
    def createCashflowsReport(self):
        pass

    @property
    def value(self):
        return self.value_
    
    @property
    def firstOrderRisk(self):
        return self.firstOrderRisk_