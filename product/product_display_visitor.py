import pandas as pd
from .product import (ProductVisitor)
from .linear_products import (ProductBulletCashflow, ProductFuture)

class CashflowVisitor(ProductVisitor):

    def visit(self, prod : ProductBulletCashflow):
        
        nvp = []
        
        this_row = ['TerminationDate']
        this_row.append(prod.terminationDate.ISO())
        nvp.append(this_row)
        
        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=['Attribute', 'Value'])

class FutureVisitor(ProductVisitor):
    
    def visit(self, prod : ProductFuture):
        
        nvp = []
        
        this_row = ['ExpirationDate']
        this_row.append(prod.expirationDate.ISO())
        nvp.append(this_row)

        this_row = ['EffectiveDate']
        this_row.append(prod.effectiveDate.ISO())
        nvp.append(this_row)

        this_row = ['MaturityDate']
        this_row.append(prod.terminationDate.ISO())
        nvp.append(this_row)
        
        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Strike']
        this_row.append(prod.strike)
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=['Attribute', 'Value'])