from __future__ import annotations
import json, os
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable
from fixedincomelib.market.basics import AccrualBasis, BusinessDayConvention, HolidayConvention
from fixedincomelib.market.indices import IndexRegistry

@dataclass(frozen=True, slots=True)
class DataConvention:
    unique_name: str
    index_key: str
    accrual_basis: str
    accrual_period: str
    payment_offset: str
    payment_biz_day_conv: str
    payment_hol_conv: str
    
    def day_count(self) -> AccrualBasis:            
        return AccrualBasis(self.accrual_basis)
    
    def biz_day_conv(self) -> BusinessDayConvention: 
        return BusinessDayConvention(self.payment_biz_day_conv)
    
    def hol_conv(self) -> HolidayConvention:         
        return HolidayConvention(self.payment_hol_conv)
    
    def index(self, tenor: Optional[str] = None):
        if tenor is None: return IndexRegistry().get(self.index_key)
        toks = self.index_key.split("-")
        if len(toks) < 2:
            raise ValueError(f"index_key '{self.index_key}' must include tenor to derive base")
        base = "-".join(toks[:-1])
        return IndexRegistry().get(base, tenor)

@dataclass(frozen=True, slots=True)
class DataConventionRFRSwap(DataConvention):
    ois_compounding: str = "COMPOUND"

@dataclass(frozen=True, slots=True)
class DataConventionRFRFuture(DataConvention):
    pass

BuilderFn = Callable[[Dict[str, Any], Dict[str, Any]], DataConvention]

class DataConventionRegistry:
    _instance: "DataConventionRegistry" | None = None
    _REQUIRED_BASE = ("index","accrual_basis","accrual_period","payment_offset","payment_biz_day_conv","payment_hol_conv")
    _DISPATCH: Dict[str, BuilderFn] = {
        "RFR SWAP":   lambda base, p: DataConventionRFRSwap(**base, ois_compounding=p.get("ois_compounding","COMPOUND")),
        "RFR FUTURE": lambda base, p: DataConventionRFRFuture(**base),
    }
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            obj = super().__new__(cls)
            obj._map: Dict[str, DataConvention] = {}
            here = os.path.dirname(__file__)
            default_path = os.path.join(here, "data_convention_registry.json")
            if os.path.exists(default_path):
                obj.load_json(default_path)
            cls._instance = obj
        return cls._instance
    def insert(self, conv: DataConvention) -> None:
        key = conv.unique_name.upper()
        if key in self._map: raise ValueError(f"duplicate unique_name '{conv.unique_name}'")
        self._map[key] = conv
    def get(self, unique_name: str) -> DataConvention:
        try: return self._map[unique_name.upper()]
        except KeyError as e: raise KeyError(f"no entry for '{unique_name}'") from e
    def load_json(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            raw: Dict[str, Dict[str, Any]] = json.load(f)
        self._load_dict(raw, source=path)
    def _load_dict(self, raw: Dict[str, Dict[str, Any]], *, source: str) -> None:
        for unique_name, payload in raw.items():
            kind = str(payload.get("kind","")).strip().upper().replace("_"," ")
            if not kind: raise ValueError(f"[{source} :: {unique_name}] Missing 'kind'")
            missing = [k for k in self._REQUIRED_BASE if k not in payload]
            if missing: raise ValueError(f"[{source} :: {unique_name}] Missing: {missing}")
            base_kwargs = dict(
                unique_name=unique_name,
                index_key=payload["index"],
                accrual_basis=payload["accrual_basis"],
                accrual_period=payload["accrual_period"],
                payment_offset=payload["payment_offset"],
                payment_biz_day_conv=payload["payment_biz_day_conv"],
                payment_hol_conv=payload["payment_hol_conv"],
            )
            builder = self._DISPATCH.get(kind)
            if builder is None:
                raise ValueError(f"[{source} :: {unique_name}] Unsupported kind: '{kind}'")
            self.insert(builder(base_kwargs, payload))
