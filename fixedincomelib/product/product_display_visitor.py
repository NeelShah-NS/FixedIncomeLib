import pandas as pd
from fixedincomelib.product.product import (ProductVisitor)
from fixedincomelib.product.linear_products import (ProductBulletCashflow, ProductFuture, ProductIborCashflow, ProductOvernightIndexCashflow, ProductRfrFuture, ProductIborSwap, ProductOvernightSwap)
from fixedincomelib.product.non_linear_products import (ProductIborCapFloorlet, ProductOvernightCapFloorlet, ProductIborCapFloor, ProductOvernightCapFloor, ProductIborSwaption, ProductOvernightSwaption)
from fixedincomelib.product.portfolio import (ProductPortfolio)

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
        this_row.append(prod.maturityDate.ISO())
        nvp.append(this_row)

        this_row = ['AccrualFactor']
        this_row.append(prod.accrualFactor)
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
    
class IborCashflowVisitor(ProductVisitor):

    def visit(self, prod: ProductIborCashflow):

        nvp = []

        this_row = ['AccrualStart']
        this_row.append(prod.accrualStart.ISO())
        nvp.append(this_row)

        this_row = ['AccrualEnd']
        this_row.append(prod.accrualEnd.ISO())
        nvp.append(this_row)

        this_row = ['AccrualFactor']
        this_row.append(prod.accrualFactor)
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.index)
        nvp.append(this_row)

        this_row = ['Spread']
        this_row.append(prod.spread)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=["Attribute", "Value"])
    
class OvernightCashflowVisitor(ProductVisitor):

    def visit(self, prod: ProductOvernightIndexCashflow):

        nvp = []

        this_row = ['EffectiveDate']
        this_row.append(prod.effectiveDate.ISO())
        nvp.append(this_row)

        this_row = ['TerminationDate']
        this_row.append(prod.terminationDate.ISO())
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.index)
        nvp.append(this_row)

        this_row = ['Compounding']
        this_row.append(prod.compounding)
        nvp.append(this_row)

        this_row = ['Spread']
        this_row.append(prod.spread)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=["Attribute", "Value"])

class RfrFutureVisitor(ProductVisitor):

    def visit(self, prod: ProductRfrFuture):

        nvp = []

        this_row = ['MaturityDate']
        this_row.append(prod.maturityDate.ISO())
        nvp.append(this_row)

        this_row = ['EffectiveDate']
        this_row.append(prod.effectiveDate.ISO())
        nvp.append(this_row)

        this_row = ['TerminationDate']
        this_row.append(prod.terminationDate.ISO())
        nvp.append(this_row)

        this_row = ['AccrualFactor']
        this_row.append(prod.accrualFactor)
        nvp.append(this_row)

        this_row = ['Compounding']
        this_row.append(prod.compounding)
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.index)
        nvp.append(this_row)

        this_row = ['Strike']
        this_row.append(prod.strike)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=["Attribute", "Value"])

class IborSwapVisitor(ProductVisitor):

    def visit(self, prod: ProductIborSwap):

        nvp = []

        this_row = ['EffectiveDate']
        this_row.append(prod.effectiveDate.ISO())
        nvp.append(this_row)

        this_row = ['MaturityDate']
        this_row.append(prod.maturityDate.ISO())
        nvp.append(this_row)

        this_row = ['FixedRate']
        this_row.append(prod.fixedRate)
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.index)
        nvp.append(this_row)

        this_row = ['PayFixed']
        this_row.append(prod.payFixed)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=["Attribute", "Value"])
    
    def listFloatingLeg(self, swap: ProductIborSwap, n: int = 3):
        return [swap.floatingLegCashflow(i).accept(IborCashflowVisitor())
                for i in range(min(n, swap.floatingLeg.count))]
    
class OvernightSwapVisitor(ProductVisitor):

    def visit(self, prod: ProductOvernightSwap):

        nvp = []

        this_row = ['EffectiveDate']
        this_row.append(prod.effectiveDate.ISO())
        nvp.append(this_row)

        this_row = ['MaturityDate']
        this_row.append(prod.maturityDate.ISO())
        nvp.append(this_row)

        this_row = ['FixedRate']
        this_row.append(prod.fixedRate)
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.index)
        nvp.append(this_row)

        this_row = ['PayFixed']
        this_row.append(prod.payFixed)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)
        
        return pd.DataFrame(nvp, columns=["Attribute", "Value"])

class IborCapFloorletVisitor(ProductVisitor):

    def visit(self, prod: ProductIborCapFloorlet) -> pd.DataFrame:

        nvp = []

        this_row = ['AccrualStart']
        this_row.append(prod.accrualStart.ISO())
        nvp.append(this_row)

        this_row = ['AccrualEnd']
        this_row.append(prod.accrualEnd.ISO())
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.index)
        nvp.append(this_row)

        this_row = ['OptionType']
        this_row.append(prod.optionType)
        nvp.append(this_row)

        this_row = ['Strike']
        this_row.append(prod.strike)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=['Attribute', 'Value'])

class OvernightCapFloorletVisitor(ProductVisitor):

    def visit(self, prod: ProductOvernightCapFloorlet) -> pd.DataFrame:

        nvp = []

        this_row = ['EffectiveDate']
        this_row.append(prod.effectiveDate.ISO())
        nvp.append(this_row)

        this_row = ['MaturityDate']
        this_row.append(prod.maturityDate.ISO())
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.index)
        nvp.append(this_row)

        this_row = ['Compounding']
        this_row.append(prod.compounding)
        nvp.append(this_row)

        this_row = ['OptionType']
        this_row.append(prod.optionType)
        nvp.append(this_row)

        this_row = ['Strike']
        this_row.append(prod.strike)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort'] 
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=['Attribute', 'Value'])


class IborCapFloorVisitor(ProductVisitor):

    def visit(self, prod: ProductIborCapFloor) -> pd.DataFrame:

        nvp = []

        this_row = ['EffectiveDate']
        this_row.append(prod.effectiveDate.ISO())
        nvp.append(this_row)

        this_row = ['MaturityDate']
        this_row.append(prod.maturityDate.ISO())
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.index)
        nvp.append(this_row)

        this_row = ['OptionType']
        this_row.append(prod.optionType)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        this_row = ['NumCaplets']
        this_row.append(len(prod.capStream.products))
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=['Attribute', 'Value'])
    
class OvernightCapFloorVisitor(ProductVisitor):

    def visit(self, prod: ProductOvernightCapFloor) -> pd.DataFrame:

        nvp = []

        this_row = ['EffectiveDate']
        this_row.append(prod.effectiveDate.ISO())
        nvp.append(this_row)

        this_row = ['MaturityDate']
        this_row.append(prod.maturityDate.ISO())
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.index)
        nvp.append(this_row)

        this_row = ['OptionType']
        this_row.append(prod.optionType)
        nvp.append(this_row)

        this_row = ['Compounding']
        this_row.append(prod.compounding)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        this_row = ['NumCaplets']
        this_row.append(len(prod.capStream.products))
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=['Attribute', 'Value'])


class IborSwaptionVisitor(ProductVisitor):

    def visit(self, prod: ProductIborSwaption) -> pd.DataFrame:

        nvp = []

        this_row = ['ExpiryDate']
        this_row.append(prod.expiryDate.ISO())
        nvp.append(this_row)

        this_row = ['SwapStart']
        this_row.append(prod.swap.effectiveDate.ISO())
        nvp.append(this_row)

        this_row = ['SwapEnd']
        this_row.append(prod.swap.maturityDate.ISO())
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.swap.index)
        nvp.append(this_row)

        this_row = ['FixedRate']
        this_row.append(prod.swap.fixedRate)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=['Attribute', 'Value'])
    
class OvernightSwaptionVisitor(ProductVisitor):

    def visit(self, prod: ProductOvernightSwaption) -> pd.DataFrame:

        nvp = []

        this_row = ['ExpiryDate']
        this_row.append(prod.expiryDate.ISO())
        nvp.append(this_row)

        this_row = ['SwapStart']
        this_row.append(prod.swap.effectiveDate.ISO())
        nvp.append(this_row)

        this_row = ['SwapEnd']
        this_row.append(prod.swap.maturityDate.ISO())
        nvp.append(this_row)

        this_row = ['Index']
        this_row.append(prod.swap.index)
        nvp.append(this_row)

        this_row = ['FixedRate']
        this_row.append(prod.swap.fixedRate)
        nvp.append(this_row)

        this_row = ['Notional']
        this_row.append(prod.notional)
        nvp.append(this_row)

        this_row = ['Currency']
        this_row.append(prod.currency.value.code())
        nvp.append(this_row)

        this_row = ['LongOrShort']
        this_row.append(prod.longOrShort.valueStr)
        nvp.append(this_row)

        return pd.DataFrame(nvp, columns=['Attribute', 'Value'])

class PortfolioVisitor(ProductVisitor):
    
    def visit(self, prod: ProductPortfolio) -> pd.DataFrame:

        nvp = []
        
        this_row = ['NumProducts']
        this_row.append(prod.numProducts)
        nvp.append(this_row)

        for idx, (p, w) in enumerate(prod.elements, start=1):
            nvp.append([f'Element {idx} Type',   p.prodType])
            nvp.append([f'Element {idx} Weight', w       ])
            
        return pd.DataFrame(nvp, columns=['Attribute', 'Value'])