from fixedincomelib.valuation.valuation_engine import ValuationEngine

class ValuationEngineRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry = {}
        return cls._instance

    def insert(self, model_name: str, prod_name: str, engine_cls: type[ValuationEngine]):
                self._registry[(model_name, prod_name)] = engine_cls

    def get(self, model_name: str, prod_name: str) -> type[ValuationEngine]:
        return self._registry.get((model_name, prod_name))

    def new_valuation_engine(self, model, val_params: dict, product) -> ValuationEngine:
        key = (model.modelType, product.prodType)
        engine_cls = self.get(*key)
        if engine_cls is None:
            raise KeyError(f"No engine registered for key {key}")
        return engine_cls(model, val_params, product)