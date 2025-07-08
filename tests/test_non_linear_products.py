# %% [markdown]
# # 🎯 Testing Non‐Linear Products
# 
# This notebook tests:
# 
# 1. **Cap/Floorlets** (IBOR & Overnight)  
# 2. **Cap/Floor Streams**  
# 3. **Cap/Floor Portfolios**  
# 4. **Swaptions** (IBOR & Overnight)  
# 5. **Visitor output** for each product
# 
# We’ll make sure each product builds the correct dates/fields and that each visitor prints the expected DataFrame.
# 
# ---
# 

# %%
from product.non_linear_products import (   
    ProductIborCapFloorlet,
    ProductOvernightCapFloorlet,
    CapFloorStream,
    ProductIborCapFloor,
    ProductOvernightCapFloor,
    ProductIborSwaption,
    ProductOvernightSwaption
)
from product.product_display_visitor import (
    IborCapFloorletVisitor,
    OvernightCapFloorletVisitor,
    IborCapFloorVisitor,
    OvernightCapFloorVisitor,
    IborSwaptionVisitor,
    OvernightSwaptionVisitor
)


# %% [markdown]
# ## 2. Cap/Floorlet: IBOR
# 
# Create a 3M IBOR caplet on 1M USD LIBOR, strike 2%, notional 1 000 000, long position.
# 

# %%
caplet_ibor = ProductIborCapFloorlet(
    startDate="2025-07-01",
    endDate="2025-10-01",
    index="USD-LIBOR-1M",
    optionType="CAP",
    strike=0.02,
    notional=1_000_000,
    longOrShort="LONG",
)
caplet_ibor

# Visitor output
caplet_ibor.accept(IborCapFloorletVisitor())



# %% [markdown]
# ## 3. Cap/Floorlet: Overnight
# 
# Create a 1-month Overnight caplet on FedFunds, compounded, strike 1%, notional 500 000, short position.
# 

# %%
caplet_ois = ProductOvernightCapFloorlet(
    effectiveDate="2025-07-01",
    termOrEnd="1M",
    index="USD-FED-FUNDS",
    compounding="COMPOUND",
    optionType="CAP",
    strike=0.01,
    notional=500_000,
    longOrShort="SHORT",
)
caplet_ois

# Visitor output
caplet_ois.accept(OvernightCapFloorletVisitor())


# %% [markdown]
# ## 4. Cap/Floor Stream
# 
# Build a quarterly (3M) cap stream from July 1 2025 to July 1 2026, strike 2.5%, notional 1 000 000.
# 

# %%
stream = CapFloorStream(
    startDate="2025-07-01",
    endDate="2026-07-01",
    frequency="3M",
    iborIndex="USD-LIBOR-3M",
    optionType="CAP",
    strike=0.025,
    notional=1_000_000,
    longOrShort="LONG",
)
print("Num caplets:", stream.numProducts)



# %%
# Show first two caplets
for i in range(2):
    print(stream.element(i).accept(IborCapFloorletVisitor()))


# %% [markdown]
# ## 5. Cap/Floor Portfolio Wrappers
# 
# ### 5.1 IBOR Cap/Floor
# 
# Wrap the above stream in a `ProductIborCapFloor`.
# 

# %%
cap = ProductIborCapFloor(
    effectiveDate="2025-07-01",
    maturityDate="2026-07-01",
    frequency="3M",
    iborIndex="USD-LIBOR-3M",
    optionType="FLOOR",
    strike=0.015,
    notional=2_000_000,
    longOrShort="SHORT",
)
cap

# Visitor output
cap.accept(IborCapFloorVisitor())


# %% [markdown]
# ### 5.2 Overnight Cap/Floor
# 
# Wrap a “compound OIS” stream in `ProductOvernightCapFloor`.
# 

# %%
cap_ois = ProductOvernightCapFloor(
    effectiveDate="2025-07-01",
    maturityDate="2026-01-01",
    frequency="1M",
    overnightIndex="USD-FED-FUNDS",
    compounding="COMPOUND",
    optionType="CAP",
    strike=0.005,
    notional=750_000,
    longOrShort="LONG",
)
cap_ois.accept(OvernightCapFloorVisitor())


# %% [markdown]
# ## 6. Swaptions
# 
# ### 6.1 IBOR Swaption
# 
# European swaption on a 5Y quarterly USD‐LIBOR swap, strike 1.75%, notional 1 000 000, long.
# 

# %%
swaption_ibor = ProductIborSwaption(
    optionExpiry="2025-12-01",
    swapStart="2026-01-01",
    swapEnd="2031-01-01",
    frequency="3M",
    iborIndex="USD-LIBOR-3M",
    strikeRate=0.0175,
    notional=1_000_000,
    longOrShort="LONG",
)
swaption_ibor.accept(IborSwaptionVisitor())


# %% [markdown]
# ### 6.2 Overnight Swaption
# 
# European swaption on a 2Y monthly OIS, strike 1%, notional 500 000, short.
# 

# %%
swaption_ois = ProductOvernightSwaption(
    optionExpiry="2025-10-01",
    swapStart="2025-11-01",
    swapEnd="2027-11-01",
    frequency="1M",
    overnightIndex="USD-FED-FUNDS",
    strikeRate=0.01,
    notional=500_000,
    longOrShort="SHORT",
)
swaption_ois.accept(OvernightSwaptionVisitor())



