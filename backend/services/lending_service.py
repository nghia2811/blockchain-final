"""
Queries lending rates from Compound V3 (Comet) and Aave V3.
Returns APY percentages for supported assets.
"""
import math
from web3 import Web3

import config

# -----------------------------------------------------------------------
# Compound V3 (Comet) ABI – only what we need for rate calculation
# -----------------------------------------------------------------------
COMET_ABI = [
    {
        "inputs": [],
        "name": "getUtilization",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "utilization", "type": "uint256"}],
        "name": "getSupplyRate",
        "outputs": [{"name": "", "type": "uint64"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "baseToken",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# -----------------------------------------------------------------------
# Aave V3 Pool ABI – getReserveData (simplified)
# -----------------------------------------------------------------------
AAVE_POOL_ABI = [
    {
        "inputs": [{"name": "asset", "type": "address"}],
        "name": "getReserveData",
        "outputs": [
            {
                "components": [
                    {"name": "configuration",       "type": "uint256"},
                    {"name": "liquidityIndex",      "type": "uint128"},
                    {"name": "currentLiquidityRate","type": "uint128"},
                    {"name": "variableBorrowIndex", "type": "uint128"},
                    {"name": "currentVariableBorrowRate", "type": "uint128"},
                    {"name": "currentStableBorrowRate",   "type": "uint128"},
                    {"name": "lastUpdateTimestamp", "type": "uint40"},
                    {"name": "id",                  "type": "uint16"},
                    {"name": "aTokenAddress",       "type": "address"},
                    {"name": "stableDebtTokenAddress",    "type": "address"},
                    {"name": "variableDebtTokenAddress",  "type": "address"},
                    {"name": "interestRateStrategyAddress","type": "address"},
                    {"name": "accruedToTreasury",   "type": "uint128"},
                    {"name": "unbacked",             "type": "uint128"},
                    {"name": "isolationModeTotalDebt","type": "uint128"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

# Seconds per year
_SECONDS_PER_YEAR = 365 * 24 * 3600


class LendingService:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(config.RPC_URL))

    # -----------------------------------------------------------------------
    # Compound V3
    # -----------------------------------------------------------------------

    def get_compound_supply_apy(self, comet_address: str = config.COMPOUND_V3_USDC) -> float:
        """
        Return the current annualised supply APY (%) for the Comet market.
        Formula: APY = (1 + ratePerSecond) ^ SECONDS_PER_YEAR - 1
        """
        try:
            comet = self.w3.eth.contract(
                address=Web3.to_checksum_address(comet_address),
                abi=COMET_ABI,
            )
            utilization = comet.functions.getUtilization().call()
            rate_per_sec = comet.functions.getSupplyRate(utilization).call()
            # rate_per_sec is scaled by 1e18 in Compound V3
            rate_per_sec_float = rate_per_sec / 1e18
            apy = ((1 + rate_per_sec_float) ** _SECONDS_PER_YEAR - 1) * 100
            return round(apy, 4)
        except Exception as e:
            print(f"[LendingService] Compound APY error: {e}")
            return 0.0

    # -----------------------------------------------------------------------
    # Aave V3
    # -----------------------------------------------------------------------

    def get_aave_supply_apy(self, asset: str = config.USDC) -> float:
        """
        Return the current annualised supply APY (%) for an Aave V3 reserve.
        currentLiquidityRate is in RAY (1e27), representing APR.
        APY = (1 + APR / SECONDS_PER_YEAR) ^ SECONDS_PER_YEAR - 1
        """
        try:
            pool = self.w3.eth.contract(
                address=Web3.to_checksum_address(config.AAVE_V3_POOL),
                abi=AAVE_POOL_ABI,
            )
            data = pool.functions.getReserveData(
                Web3.to_checksum_address(asset)
            ).call()
            # currentLiquidityRate is index 2 of the returned tuple
            liquidity_rate_ray = data[2]
            apr = liquidity_rate_ray / 1e27  # convert from RAY
            apy = ((1 + apr / _SECONDS_PER_YEAR) ** _SECONDS_PER_YEAR - 1) * 100
            return round(apy, 4)
        except Exception as e:
            print(f"[LendingService] Aave APY error: {e}")
            return 0.0

    # -----------------------------------------------------------------------
    # Best protocol comparison
    # -----------------------------------------------------------------------

    def get_best_lending_opportunity(self, asset_symbol: str = "USDC") -> dict:
        """
        Compare Compound and Aave rates and return the better option.
        """
        token_meta = config.TOKENS.get(asset_symbol)
        if not token_meta:
            return {}
        
        asset_address = token_meta.get("address")
        
        if asset_symbol == "ETH":
            # For ETH, we still check the WETH reserve in Aave to get APY
            aave_apy = self.get_aave_supply_apy(config.WETH)
            return {
                "protocol":         "Aave V3 WETH Gateway",
                "protocol_address": config.AAVE_V3_WETH_GATEWAY,
                "apy":              aave_apy,
                "asset":            "ETH",
                "asset_symbol":     "ETH",
            }
            
        if not asset_address:
            return {}

        aave_apy = self.get_aave_supply_apy(asset_address)

        if asset_symbol == "USDC":
            compound_apy = self.get_compound_supply_apy()
            if compound_apy >= aave_apy:
                return {
                    "protocol":         "Compound V3",
                    "protocol_address": config.COMPOUND_V3_USDC,
                    "apy":              compound_apy,
                    "asset":            asset_address,
                    "asset_symbol":     asset_symbol,
                }

        return {
            "protocol":         "Aave V3",
            "protocol_address": config.AAVE_V3_POOL,
            "apy":              aave_apy,
            "asset":            asset_address,
            "asset_symbol":     asset_symbol,
        }
