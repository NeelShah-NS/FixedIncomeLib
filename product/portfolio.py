from typing import List, Optional
from product.product import Product

class ProductPortfolio:
    prodType = "ProductPortfolio"
    
    def __init__(self, products: List[Product], weights: Optional[List[float]] = None):
        assert products, "Portfolio must contain at least one product"
        self.products = products
        self.weights  = weights or [1.0]*len(products)

    @property
    def numProducts(self):
        return len(self.products)

    def element(self, i: int) -> Product:
        assert 0 <= i < self.numProducts
        return self.products[i]

