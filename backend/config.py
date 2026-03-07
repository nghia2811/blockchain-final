"""
Central configuration loaded from environment / .env file.
"""
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)


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
AAVE_V3_WETH_GATEWAY: str = os.getenv(
    "AAVE_V3_WETH_GATEWAY", "0xd01607c3C5eCABa394D8be377a08590149325722"
)

# -----------------------------------------------------------------------
# Strategy thresholds
# -----------------------------------------------------------------------
ARBITRAGE_MIN_SPREAD_PCT: float = float(os.getenv("ARBITRAGE_MIN_SPREAD_PCT", "0.0"))
LENDING_MIN_APY_PCT: float      = float(os.getenv("LENDING_MIN_APY_PCT", "1.0"))
PRICE_STALE_SECONDS: int        = int(os.getenv("PRICE_STALE_SECONDS", "3600"))

# -----------------------------------------------------------------------
# Token registry
# Default mainnet addresses / Chainlink USD feeds / suggested trade amounts.
#
# Override individual tokens via env vars (e.g. WETH=0x...) or inject
# completely new tokens at runtime via:
#   EXTRA_TOKENS_JSON='{"AAVE":{"address":"0x7Fc...","decimals":18,
#                        "chainlink_usd":"0x547...","default_amount":1000000000000000000}}'
# -----------------------------------------------------------------------
_TOKEN_DEFAULTS: dict = {
    "ETH": {
        "address":        "ETH",
        "decimals":       18,
        "chainlink_usd":  os.getenv("CHAINLINK_ETH_USD",  "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"),
        "default_amount": int(0.1 * 10 ** 18),
    },
    "WETH": {
        "address":        os.getenv("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
        "decimals":       18,
        "chainlink_usd":  os.getenv("CHAINLINK_ETH_USD",  "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"),
        "default_amount": int(0.1 * 10 ** 18),
    },
    "WBTC": {
        "address":        os.getenv("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"),
        "decimals":       8,
        "chainlink_usd":  os.getenv("CHAINLINK_BTC_USD",  "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c"),
        "default_amount": int(0.001 * 10 ** 8),
    },
    "USDC": {
        "address":        os.getenv("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
        "decimals":       6,
        "chainlink_usd":  os.getenv("CHAINLINK_USDC_USD", "0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6"),
        "default_amount": 1_000 * 10 ** 6,
    },
    "LINK": {
        "address":        os.getenv("LINK", "0x514910771AF9Ca656af840dff83E8264EcF986CA"),
        "decimals":       18,
        "chainlink_usd":  os.getenv("CHAINLINK_LINK_USD", "0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c"),
        "default_amount": int(10 * 10 ** 18),
    },
    "UNI": {
        "address":        os.getenv("UNI",  "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"),
        "decimals":       18,
        "chainlink_usd":  os.getenv("CHAINLINK_UNI_USD",  "0x553303d460EE0afB37EdFf9bE42922D8FF63220e"),
        "default_amount": int(10 * 10 ** 18),
    },
}


def _build_tokens() -> dict:
    tokens = dict(_TOKEN_DEFAULTS)
    extra_json = os.getenv("EXTRA_TOKENS_JSON", "")
    if extra_json:
        try:
            tokens.update(json.loads(extra_json))
        except json.JSONDecodeError as e:
            print(f"[config] Invalid EXTRA_TOKENS_JSON: {e}")
    return tokens


TOKENS: dict = _build_tokens()

# -----------------------------------------------------------------------
# Arbitrage pair list
# Each entry: token0, token1 (symbols from TOKENS), pool_address, fee (bps).
# The engine will determine canonical pool ordering at runtime via token0()
# and token1() on the pool contract.
#
# Override all pairs at runtime via:
#   ARBITRAGE_PAIRS_JSON='[{"token0":"WETH","token1":"USDC","pool_address":"0x...","fee":500}]'
# -----------------------------------------------------------------------
_PAIR_DEFAULTS: list = [
    {
        "token0": "WETH",
        "token1": "USDC",
        "pool_address": os.getenv("POOL_WETH_USDC", "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"),
        "fee": 500,
    },
    {
        "token0": "WETH",
        "token1": "WBTC",
        "pool_address": os.getenv("POOL_WETH_WBTC", "0xCBCdF9626bC03E24f779434178A73a0B4bad62eD"),
        "fee": 3000,
    },
    {
        "token0": "WBTC",
        "token1": "USDC",
        "pool_address": os.getenv("POOL_WBTC_USDC", "0x99ac8cA7087fA4A2A1FB6357269965A2014ABc35"),
        "fee": 3000,
    },
    {
        "token0": "LINK",
        "token1": "WETH",
        "pool_address": os.getenv("POOL_LINK_WETH", "0xa6Cc3C2531FdaA6Ae1A3CA84c2855806728693e8"),
        "fee": 3000,
    },
    {
        "token0": "UNI",
        "token1": "WETH",
        "pool_address": os.getenv("POOL_UNI_WETH", "0x1d42064Fc4Beb5F8aAF85F4617AE8b3b5B8Bd801"),
        "fee": 3000,
    },
]


def _build_pairs() -> list:
    override_json = os.getenv("ARBITRAGE_PAIRS_JSON", "")
    if override_json:
        try:
            return json.loads(override_json)
        except json.JSONDecodeError as e:
            print(f"[config] Invalid ARBITRAGE_PAIRS_JSON: {e}")
    return list(_PAIR_DEFAULTS)


ARBITRAGE_PAIRS: list = _build_pairs()

# -----------------------------------------------------------------------
# Convenience aliases used by lending_service and calldata router
# -----------------------------------------------------------------------
WETH: str = TOKENS["WETH"]["address"]
WBTC: str = TOKENS["WBTC"]["address"]
USDC: str = TOKENS["USDC"]["address"]
