from __future__ import annotations
from typing import Callable, Any, Dict, Type
from fixedincomelib.conventions.data_conventions import DataConvention

class ProductBuilderRegistry:
    _instance: "ProductBuilderRegistry" | None = None

    def __new__(cls):
        if cls._instance is None:
            obj = super().__new__(cls)
            obj._registry: Dict[Type[DataConvention], Callable[..., Any]] = {}
            cls._instance = obj
        return cls._instance

    def insert(self, conv_cls: Type[DataConvention], builder: Callable[..., Any]) -> None:
        self._registry[conv_cls] = builder

    def get(self, conv_cls: Type[DataConvention]):
        return self._registry.get(conv_cls)

    def new_product(
        self,
        conv: DataConvention, *,
        value_date: str,
        axis_entry,
        value: float,
        notional: float | None,
        long_or_short: str,
    ):
        conv_cls = type(conv)
        builder = self.get(conv_cls)
        if builder is None:
            raise KeyError(f"No product builder registered for {conv_cls.__name__}")
        return builder(
            conv,
            value_date=value_date,
            axis_entry=axis_entry,
            value=value,
            notional=notional,
            long_or_short=long_or_short,
        )