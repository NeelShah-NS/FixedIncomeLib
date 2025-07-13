import pandas as pd
import datetime as dt
from typing import Any, Optional
from abc import ABCMeta, abstractmethod
from date import Date

### allowed model type
class ModelType:

    YIELD_CURVE = 1
    IR_SABR = 2
    INVALID = 3

    def __init__(self, model_type : str) -> None:
        self.valueStr_ = model_type
        self.value_ = ModelType.INVALID
        if model_type.upper() == 'YIELD_CURVE':
            self.value_ =  ModelType.YIELD_CURVE
        elif model_type.upper() == 'IR_SABR':
            self.value_ =  ModelType.IR_SABR
        else:
            raise Exception('Model type ' + model_type + ' is not supported.')
    
    @property
    def value(self):
        return self.value_
    
    @property
    def valueStr(self):
        return self.valueStr_

### model interface
class Model(metaclass=ABCMeta):

    def __init__(self, 
                valueDate : str, 
                modelType : str, 
                dataCollection : pd.DataFrame, 
                buildMethodCollection : list) -> None:

        self.valueDate_ = Date(valueDate)
        self.modelType_ = ModelType(modelType)
        self.dataCollection_ = dataCollection
        self.buildMethodCollection_ = buildMethodCollection
        self.subModel_ = None
        # initialize model component
        self.components = dict()
        for this_bm in self.buildMethodCollection:
            assert isinstance(this_bm, dict)
            assert 'TARGET' in list(this_bm.keys())
            tgt = this_bm['TARGET']
            val = this_bm.get('VALUES', None)
            if val:
                key = f"{tgt}-{val}".upper()
            else:
                key = tgt.upper()
            self.components[key] = self.newModelComponent(this_bm)

    @abstractmethod
    def newModelComponent(self, buildMethod : dict):
        pass

    @property    
    def valueDate(self):
        return self.valueDate_
    
    @property
    def modelType(self):
        return self.modelType_.valueStr

    @property
    def buildMethodCollection(self):
        return self.buildMethodCollection_
    
    @property
    def dataCollection(self):
        return self.dataCollection_
    
    @property
    def subModel(self):
        return self.subModel_

    def retrieveComponent(self, target : str):
        return self.components.get(target.upper())

### one model can have multiple components
class ModelComponent(metaclass=ABCMeta):

    def __init__(self, 
                valueDate : Date, 
                dataCollection : pd.DataFrame, 
                buildMethod : dict) -> None:

        self.valueDate_ = valueDate
        self.dataCollection_ = dataCollection
        self.buildMethod_ = buildMethod
        self.target_ = buildMethod['TARGET']
        self.stateVars_ = []

    @abstractmethod
    def calibrate(self):
        pass

    @property
    def target(self):
        return self.target_





