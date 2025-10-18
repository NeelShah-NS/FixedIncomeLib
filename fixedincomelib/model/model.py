import pandas as pd
import datetime as dt
from typing import Any, Dict, List, Optional
from abc import ABCMeta, abstractmethod
from fixedincomelib.date import Date
from fixedincomelib.data import DataCollection

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
                dataCollection : DataCollection, 
                buildMethodCollection : List[Dict[str, Any]]) -> None:

        self.valueDate_ = Date(valueDate)
        self.modelType_ = ModelType(modelType)
        self.dataCollection_ = dataCollection
        self.buildMethodCollection_ = buildMethodCollection
        self.subModel_ = None
        # initialize model component
        self.components: Dict[str, ModelComponent] = {}
        for this_bm in self.buildMethodCollection:
            assert isinstance(this_bm, dict)
            assert 'TARGET' in list(this_bm.keys())
            tgt = this_bm['TARGET']
            val = this_bm.get('VALUES', None)
            if val:
                key = f"{tgt}-{val}".upper()
            else:
                key = tgt.upper()

            prod = this_bm.get("PRODUCT")
            if prod:
                key = f"{key}-{prod}".upper()

            self.components[key] = self.newModelComponent(this_bm)

    @abstractmethod
    def newModelComponent(self, buildMethod : dict):
        pass

    @abstractmethod
    def jacobian(self):
        """
        Build the model Jacobian J_{X^M / X^I}.
        Rows = calibration instruments across all components.
        Columns = internal model parameters (concatenated by component).
        """
        raise NotImplementedError
    

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
    
    def perturbModelParameter(self, target: str, state_var_index: int, perturb_size: float) -> None:
        comp = self.retrieveComponent(target)
        if comp is None:
            raise KeyError(f"Component '{target}' not found. Known: {list(self.components.keys())}")
        comp.perturbModelParameter(state_var_index, perturb_size)

### one model can have multiple components
class ModelComponent(metaclass=ABCMeta):

    def __init__(self, 
                valueDate : Date, 
                dataCollection : DataCollection, 
                buildMethod :  Dict[str, Any]) -> None:

        self.valueDate_ = valueDate
        self.dataCollection_ = dataCollection
        self.buildMethod_ = buildMethod
        self.target_ = buildMethod['TARGET']
        self.stateVars_ : List[float] = []

    @abstractmethod
    def calibrate(self):
        pass

    @property
    def target(self):
        return self.target_
    
    @property
    def dataCollection(self) -> Any:
        return self.dataCollection_
    
    def perturbModelParameter(self, state_var_index: int, perturb_size: float) -> None:
        arr = self.stateVars_
        n = len(arr)
        if not (0 <= state_var_index < n):
            raise IndexError(f"{self.target}: state_var_index {state_var_index} out of range [0,{n-1}]")
        
        arr[state_var_index] = float(arr[state_var_index]) + float(perturb_size)