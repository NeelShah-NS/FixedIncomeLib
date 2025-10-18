from typing import Dict, Tuple, Iterable
from fixedincomelib.data.base import MarketData

class DataCollection:

    def __init__(self, dataList: Iterable[MarketData]):
        self.dataMap: Dict[Tuple[str, str], MarketData] = {}

        for each in dataList:
            key = (each.data_type, each.data_convention)
            if key in self.dataMap:
                raise KeyError(f"Duplicate data for key {key}")
            self.dataMap[key] = each

    def getDataFromDataCollection(
        self,
        data_type: str,
        data_convention: str
    ) -> MarketData:
        key = (data_type, data_convention)
        if key not in self.dataMap:
            raise KeyError(f"No data for key {key}")
        return self.dataMap[key]
    
    def clear(self) -> None:
        self.dataMap.clear()

    get = getDataFromDataCollection
