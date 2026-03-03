"""
Investment Strategy Backend
FastAPI application that analyses on-chain data (Chainlink price feeds,
Uniswap V3 pools, Compound / Aave lending rates) and returns strategy
recommendations to the multisig wallet frontend.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import prices, strategies, calldata

app = FastAPI(
    title="Multisig Investment Strategy API",
    description=(
        "Generates lending and arbitrage strategy recommendations "
        "for the Group Multisig Asset Manager."
    ),
    version="1.0.0",
)

# Allow the local frontend (served by python -m http.server) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(prices.router)
app.include_router(strategies.router)
app.include_router(calldata.router)


@app.get("/")
def root():
    return {
        "service": "Multisig Investment Strategy API",
        "docs":    "/docs",
        "endpoints": {
            "prices":      "/api/prices",
            "strategies":  "/api/strategies/opportunities",
            "lending":     "/api/strategies/lending",
            "arbitrage":   "/api/strategies/arbitrage",
            "scan":        "/api/strategies/scan",
            "calldata":    "/api/calldata/encode  [POST]",
        },
    }
