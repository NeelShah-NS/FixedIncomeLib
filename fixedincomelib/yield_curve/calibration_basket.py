from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable, List

@dataclass(frozen=True)
class CalibItem:
    product: Any
    quote: float
    data_type: str
    data_convention: str
    axis: Any

class CalibrationBasket:
    def __init__(self, items: Iterable[CalibItem] = ()) -> None:
        self._items: List[CalibItem] = list(items)

    def add(self, item: CalibItem) -> None:
        self._items.append(item)

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def products(self) -> List[Any]:
        return [it.product for it in self._items]

    def quotes(self) -> List[float]:
        return [it.quote for it in self._items]

    def by_type(self, kind: str) -> List[CalibItem]:
        k = kind.upper()
        return [it for it in self._items if it.data_type.upper() == k]
