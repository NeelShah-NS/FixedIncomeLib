from dataclasses import dataclass
from typing import Optional, Any
from date import Date
from product import Product

@dataclass
class PillarNode:
    node_id: str               
    pillar_index: int          
    pillar_time: float         
    pillar_date: Date           
    start_date: Optional[Date]  
    end_date: Optional[Date]    
    instrument: Product
    state_value: float = 0.0
