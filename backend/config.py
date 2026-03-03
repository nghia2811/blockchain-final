"""
Central configuration loaded from environment / .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key}")
    return val


# -----------------------------------------------------------------------
# RPC & contract
# -----------------------------------------------------------------------
RPC_URL: str = os.getenv("RPC_URL", "http://127.0.0.1:8545")
CONTRACT_ADDRESS: str = os.getenv("CONTRACT_ADDRESS", "")

# -----------------------------------------------------------------------
# Chainlink Price Feeds
# -----------------------------------------------------------------------
CHAINLINK_ETH_USD: str = os.getenv(
    "CHAINLINK_ETH_USD", "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
)
CHAINLINK_BTC_USD: str = os.getenv(
    "CHAINLINK_BTC_USD", "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c"
)

# -----------------------------------------------------------------------
# Protocol addresses
# -----------------------------------------------------------------------
UNISWAP_V3_ROUTER: str = os.getenv(
    "UNISWAP_V3_ROUTER", "0xE592427A0AEce92De3Edee1F18E0157C05861564"
)
COMPOUND_V3_USDC: str = os.getenv(
    "COMPOUND_V3_USDC", "0xc3d688B66703497DAA19211EEdff47f25384cdc3"
)
AAVE_V3_POOL: str = os.getenv(
    "AAVE_V3_POOL", "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
)

# -----------------------------------------------------------------------
# Token addresses
# -----------------------------------------------------------------------
WETH: str  = os.getenv("WETH",  "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
WBTC: str  = os.getenv("WBTC",  "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599")
USDC: str  = os.getenv("USDC",  "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")

# Uniswap V3 WETH/WBTC pool (0.3% fee)
UNISWAP_WETH_WBTC_POOL: str = os.getenv(
    "UNISWAP_WETH_WBTC_POOL", "0xCBCdF9626bC03E24f779434178A73a0B4bad62eD"
)

# -----------------------------------------------------------------------
# Strategy thresholds
# -----------------------------------------------------------------------
ARBITRAGE_MIN_SPREAD_PCT: float = float(os.getenv("ARBITRAGE_MIN_SPREAD_PCT", "0.3"))
LENDING_MIN_APY_PCT: float      = float(os.getenv("LENDING_MIN_APY_PCT", "1.0"))
PRICE_STALE_SECONDS: int        = int(os.getenv("PRICE_STALE_SECONDS", "3600"))
