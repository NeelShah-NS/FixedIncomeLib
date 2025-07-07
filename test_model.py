import pandas as pd
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
    # test model building
    data_collection = pd.DataFrame(DUMMY_DATA_COLLECTION, columns=['INDEX', 'AXIS1', 'VALUES'])
    build_method_collection = DUMMY_BUILD_METHOD
    model = YieldCurve(value_date, data_collection, build_method_collection)
    # test discounting
    print(model.discountFactor('SOFR-1B', '2025-06-25'))
    print(model.discountFactor('USD-LIBOR-BBA-3M', '2025-06-25'))
    print(model.forward('SOFR-1B', '2025-06-25', '2025-07-25'))
    print(model.forward('USD-LIBOR-BBA-3M', '2025-06-25'))