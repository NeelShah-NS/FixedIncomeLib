from product import *

if __name__ == '__main__':

    # test product cashflow
    maturity_date = '2025-12-31'
    currency = 'USD'
    notional = 1e4
    longOrShort = 'Long'
    this_prod = ProductBulletCashflow(maturity_date, currency, notional, longOrShort)
    this_displayer = CashflowVisitor()
    print(this_prod.accept(this_displayer))

    # test product cashflow
    effective_date = '2025-12-31'
    index = 'USD-LIBOR-BBA-3M'
    strike = 98.
    this_prod = ProductFuture(
        effective_date, 
        index , 
        strike,
        notional,
        longOrShort)
    this_displayer = FutureVisitor()
    print(this_prod.accept(this_displayer))