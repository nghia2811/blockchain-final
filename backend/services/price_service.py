"""
Reads price data from Chainlink on-chain feeds and Uniswap V3 pool slots.
"""
import time
import math
from web3 import Web3

import config
from models.strategy import PriceSnapshot

# Minimal Chainlink AggregatorV3Interface ABI
AGGREGATOR_ABI = [
    {
        "inputs": [],
        "name": "latestRoundData",
        "outputs": [
            {"name": "roundId",         "type": "uint80"},
            {"name": "answer",          "type": "int256"},
            {"name": "startedAt",       "type": "uint256"},
            {"name": "updatedAt",       "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Uniswap V3 Pool slot0 ABI (only what we need)
UNISWAP_V3_POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"name": "sqrtPriceX96",               "type": "uint160"},
            {"name": "tick",                        "type": "int24"},
            {"name": "observationIndex",            "type": "uint16"},
            {"name": "observationCardinality",      "type": "uint16"},
            {"name": "observationCardinalityNext",  "type": "uint16"},
            {"name": "feeProtocol",                 "type": "uint8"},
            {"name": "unlocked",                    "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class PriceService:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
        self._eth_feed  = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.CHAINLINK_ETH_USD),
            abi=AGGREGATOR_ABI,
        )
        self._btc_feed  = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.CHAINLINK_BTC_USD),
            abi=AGGREGATOR_ABI,
        )

    # -----------------------------------------------------------------------
    # Chainlink helpers
    # -----------------------------------------------------------------------

    def _read_feed(self, contract) -> dict:
        _, answer, _, updated_at, _ = contract.functions.latestRoundData().call()
        decimals = contract.functions.decimals().call()
        price = answer / (10 ** decimals)
        is_fresh = (int(time.time()) - updated_at) <= config.PRICE_STALE_SECONDS
        return {"price": price, "updated_at": updated_at, "is_fresh": is_fresh}

    def get_eth_usd(self) -> dict:
        return self._read_feed(self._eth_feed)

    def get_btc_usd(self) -> dict:
        return self._read_feed(self._btc_feed)

    def get_price_snapshot(self) -> PriceSnapshot:
        eth = self.get_eth_usd()
        btc = self.get_btc_usd()
        return PriceSnapshot(
            eth_usd=eth["price"],
            btc_usd=btc["price"],
            eth_btc_ratio=eth["price"] / btc["price"] if btc["price"] else 0,
            updated_at=min(eth["updated_at"], btc["updated_at"]),
            is_fresh=eth["is_fresh"] and btc["is_fresh"],
        )

    # -----------------------------------------------------------------------
    # Uniswap V3 pool price  (token1/token0 expressed in token0 units)
    # -----------------------------------------------------------------------

    def get_uniswap_v3_spot_price(
        self,
        pool_address: str,
        token0_decimals: int = 18,
        token1_decimals: int = 8,
    ) -> float:
        """
        Decode sqrtPriceX96 from a Uniswap V3 pool's slot0.

        Returns price of token0 denominated in token1 units
        (e.g. for WETH/WBTC pool → ETH price in BTC).
        """
        pool = self.w3.eth.contract(
            address=Web3.to_checksum_address(pool_address),
            abi=UNISWAP_V3_POOL_ABI,
        )
        sqrt_price_x96 = pool.functions.slot0().call()[0]
        if sqrt_price_x96 == 0:
            return 0.0

        # price = (sqrtPriceX96 / 2^96)^2 * (10^decimals0 / 10^decimals1)
        price_raw = (sqrt_price_x96 / (2 ** 96)) ** 2
        price = price_raw * (10 ** token0_decimals) / (10 ** token1_decimals)
        return price

    def get_weth_wbtc_dex_price(self) -> float:
        """
        ETH price expressed in BTC from the Uniswap V3 WETH/WBTC pool.
        WETH decimals=18, WBTC decimals=8.
        """
        return self.get_uniswap_v3_spot_price(
            config.UNISWAP_WETH_WBTC_POOL,
            token0_decimals=18,
            token1_decimals=8,
        )
