import csv
import os
from fixedincomelib.date import Date
from typing import Dict
import datetime as _dt

class IndexManager:
    
    _MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
    FIXING_PATH = os.path.normpath(os.path.join(_MODULE_DIR, os.pardir, "fixings", "fixings.csv"))
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IndexManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self._fixings: Dict[str, Dict[Date, float]] = {}
        self.load_fixings_from_csv(IndexManager.FIXING_PATH)

    @classmethod
    def instance(cls) -> "IndexManager":
        return cls()

    def add_fixing(self, index_name: str, fixing_date: Date, rate: float) -> None:
        self._fixings.setdefault(index_name, {})[fixing_date] = rate

    def add_fixings(self, index_name: str, fixings: dict[Date, float]) -> None:
        self._fixings.setdefault(index_name, {}).update(fixings)

    def get_fixing(self, index_name: str, target_date: Date) -> float:
        try:
            return self._fixings[index_name][target_date]
        except KeyError:
            raise KeyError(f"No fixing for index '{index_name}' on date {target_date}")

    def get_fixings(
        self,
        index_name: str,
        start_date: Date,
        end_date: Date
    ) -> dict[Date, float]:
        index_data = self._fixings.get(index_name, {})
        return {
            dt: rate
            for dt, rate in index_data.items()
            if start_date <= dt < end_date
        }

    def load_fixings_from_csv(self, file_path: str) -> None:
        with open(file_path, newline='') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for record in csv_reader:
                idx_key     = record["index_key"]
                raw = record["date"].split()[0]
                date_string = _dt.datetime.strptime(raw, "%m/%d/%Y").date()
                rate_value  = float(record["fixing"])
                fixing_date = Date(date_string)
                self.add_fixing(idx_key, fixing_date, rate_value)
