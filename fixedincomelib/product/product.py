import numpy as np
import pandas as pd
from abc import ABCMeta, abstractmethod
from fixedincomelib.date import (Date)
from fixedincomelib.market import (Currency)

class LongOrShort:
    
    LONG = 1
    SHORT = 2
    INVALID = 3

    def __init__(self, longOrShort : str) -> None:
        self.valueStr_ = longOrShort
        self.value_ = LongOrShort.INVALID        
        if longOrShort.upper() == 'LONG':
            self.value_ = LongOrShort.LONG
        elif longOrShort.upper() == 'SHORT':
            self.value_ = LongOrShort.SHORT
    
    @property
    def value(self):
        return self.value_
    
    @property
    def valueStr(self):
        return self.valueStr_

class ProductVisitor(metaclass=ABCMeta):
    pass
    
class Product(metaclass=ABCMeta):

    def __init__(self, firstDate : Date, lastDate : Date, notional : float, longOrShort : str, currency : Currency) -> None:
        self.firstDate_ = firstDate
        self.lastDate_ = lastDate
        self.notional_ = notional
        self.longOrShort_ = LongOrShort(longOrShort)
        self.currency_ = currency

    @abstractmethod
    def accept(self, visitor: ProductVisitor):
        pass
    
    @property
    def prodType(self):
        pass

    @property
    def firstDate(self):
        return self.firstDate_
    
    @property
    def lastDate(self):
        return self.lastDate_

    @property
    def notional(self):
        return self.notional_
    
    @property
    def longOrShort(self):
        return self.longOrShort_
    
    @property
    def currency(self):
        return self.currency_


