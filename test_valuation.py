import pandas as pd
from product import *
from yield_curve import *

# make up data (you can read in some flat file (.csv)
DUMMY_DATA_COLLECTION = [
    ['SOFR-1B', '1M', 0.03],
    ['SOFR-1B', '3M', 0.0325],
    ['SOFR-1B', '6M', 0.035],
    ['SOFR-1B', '1Y', 0.0375],
    ['USD-LIBOR-BBA-3M', '1M', 0.04],
    ['USD-LIBOR-BBA-3M', '3M', 0.0425],
    ['USD-LIBOR-BBA-3M', '6M', 0.045],
    ['USD-LIBOR-BBA-3M', '1Y', 0.0475]]
# make up build method collection
DUMMY_BUILD_METHOD = [
    {'TARGET' : 'SOFR-1B', 'INTERPOLATION METHOD' : 'PIECEWISE_CONSTANT'},
    {'TARGET' : 'USD-LIBOR-BBA-3M', 'INTERPOLATION METHOD' : 'PIECEWISE_CONSTANT'}
]


if __name__ == '__main__':

    value_date = '2025-05-25'
    
    # model 
    data_collection = pd.DataFrame(DUMMY_DATA_COLLECTION, columns=['INDEX', 'AXIS1', 'VALUES'])
    build_method_collection = DUMMY_BUILD_METHOD
    model = YiedCurve(value_date, data_collection, build_method_collection)
    
    # val_param
    valuation_parameters = {'FUNDING INDEX' : 'SOFR-1B'}

    # product 
    termination_date = '2028-05-25'
    currency = 'USD'
    notional = 1e6
    long_or_short = 'long'
    product_bullet = ProductBulletCashflow(termination_date, currency, notional, long_or_short)

    # test valuation
    ve = ValuationEngineProductBulletCashflow(model, valuation_parameters, product_bullet)
    ve.calculateValue()
    print(ve.value)