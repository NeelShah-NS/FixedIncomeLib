from typing import List, Optional, Tuple
from fixedincomelib.product.product import Product

class ProductPortfolio(Product):
    prodType = "ProductPortfolio"

    def __init__(self, products: List[Product], weights: Optional[List[float]] = None):
        assert products, "Portfolio must contain at least one product"
        if weights is None:
            weights = [1.0] * len(products)
        assert len(weights) == len(products), "Weights list must match products list length"
        self.elements: List[Tuple[Product, float]] = list(zip(products, weights))

        for attr in ("notional", "coupon", "maturity"):
            try:
                setattr(self, attr, None)
            except AttributeError:
                pass

    @property
    def numProducts(self):
        return len(self.elements)

    def element(self, i: int) -> Product:
        assert 0 <= i < self.numProducts
        return self.elements[i][0]

    def accept(self, visitor):
        visitor.visit_portfolio(self)
        for prod, _ in self.elements:
            prod.accept(visitor)