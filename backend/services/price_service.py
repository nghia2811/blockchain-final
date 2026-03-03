"""
Reads price data from Chainlink on-chain feeds and Uniswap V3 pool slots.
"""
import time
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

# Uniswap V3 Pool ABI — slot0 + token0 + token1
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
        # Cache: feed address → contract object
        self._feed_cache: dict = {}

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _get_feed(self, feed_address: str):
        addr = Web3.to_checksum_address(feed_address)
        if addr not in self._feed_cache:
            self._feed_cache[addr] = self.w3.eth.contract(address=addr, abi=AGGREGATOR_ABI)
        return self._feed_cache[addr]

    def _read_feed(self, contract) -> dict:
        _, answer, _, updated_at, _ = contract.functions.latestRoundData().call()
        decimals = contract.functions.decimals().call()
        price    = answer / (10 ** decimals)
        is_fresh = (int(time.time()) - updated_at) <= config.PRICE_STALE_SECONDS
        return {"price": price, "updated_at": updated_at, "is_fresh": is_fresh}

    # -----------------------------------------------------------------------
    # Single-token USD price (reads the Chainlink feed from TOKENS registry)
    # -----------------------------------------------------------------------

    def get_token_usd_price(self, symbol: str) -> dict:
        """
        Return {price, updated_at, is_fresh} for any token in config.TOKENS.
        """
        token = config.TOKENS.get(symbol)
        if not token:
            raise ValueError(f"Unknown token symbol: {symbol}")
        feed_address = token.get("chainlink_usd")
        if not feed_address:
            raise ValueError(f"No Chainlink USD feed configured for {symbol}")
        return self._read_feed(self._get_feed(feed_address))

    def get_all_token_prices(self) -> dict[str, float]:
        """
        Read USD prices for every token in config.TOKENS that has a Chainlink feed.
        Returns {symbol: usd_price}.  Skips tokens whose feed call fails.
        """
        prices: dict[str, float] = {}
        for symbol, meta in config.TOKENS.items():
            if not meta.get("chainlink_usd"):
                continue
            try:
                result = self.get_token_usd_price(symbol)
                prices[symbol] = result["price"]
            except Exception as e:
                print(f"[PriceService] Failed to fetch {symbol}/USD: {e}")
        return prices

    # -----------------------------------------------------------------------
    # Backward-compat helpers (ETH and BTC)
    # -----------------------------------------------------------------------

    def get_eth_usd(self) -> dict:
        return self.get_token_usd_price("WETH")

    def get_btc_usd(self) -> dict:
        return self.get_token_usd_price("WBTC")

    def get_price_snapshot(self) -> PriceSnapshot:
        eth        = self.get_eth_usd()
        btc        = self.get_btc_usd()
        all_prices = self.get_all_token_prices()
        return PriceSnapshot(
            eth_usd=eth["price"],
            btc_usd=btc["price"],
            eth_btc_ratio=eth["price"] / btc["price"] if btc["price"] else 0,
            updated_at=min(eth["updated_at"], btc["updated_at"]),
            is_fresh=eth["is_fresh"] and btc["is_fresh"],
            token_prices=all_prices,
        )

    # -----------------------------------------------------------------------
    # Uniswap V3 pool price
    # -----------------------------------------------------------------------

    def get_pool_price_ratio(self, pair: dict) -> tuple[float, str | None]:
        """
        Compute the DEX price ratio for a pair config entry.

        The pair dict has keys: token0, token1 (symbols), pool_address, fee.
        The Uniswap pool stores prices using *canonical* address ordering, which
        may differ from the pair config order.  This method:
          1. Reads pool.token0() and pool.token1() to get canonical addresses.
          2. Matches them to config.TOKENS symbols.
          3. Decodes sqrtPriceX96 → price of canonical_token1 per canonical_token0.
          4. Re-inverts if the pair config has the tokens in the opposite order,
             so the result is always: (price of pair['token1'] per pair['token0']).

        Returns (ratio, error_str).  error_str is None on success.
        """
        pool_address = pair["pool_address"]
        sym0 = pair["token0"]   # as specified in the pair config
        sym1 = pair["token1"]

        meta0 = config.TOKENS.get(sym0)
        meta1 = config.TOKENS.get(sym1)
        if not meta0 or not meta1:
            return 0.0, f"Unknown token symbol(s): {sym0}, {sym1}"

        try:
            pool = self.w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=UNISWAP_V3_POOL_ABI,
            )

            sqrt_price_x96  = pool.functions.slot0().call()[0]
            pool_token0_addr = pool.functions.token0().call().lower()
            pool_token1_addr = pool.functions.token1().call().lower()

            if sqrt_price_x96 == 0:
                return 0.0, "sqrtPriceX96 is 0"

            # Find which symbol corresponds to the pool's canonical token0
            addr0 = meta0["address"].lower()
            addr1 = meta1["address"].lower()

            if pool_token0_addr == addr0 and pool_token1_addr == addr1:
                # Pair config matches canonical pool ordering
                dec0, dec1 = meta0["decimals"], meta1["decimals"]
                inverted = False
            elif pool_token0_addr == addr1 and pool_token1_addr == addr0:
                # Pair config is reversed relative to pool canonical ordering
                dec0, dec1 = meta1["decimals"], meta0["decimals"]
                inverted = True
            else:
                return 0.0, (
                    f"Pool token addresses do not match config. "
                    f"Pool: {pool_token0_addr}/{pool_token1_addr}  "
                    f"Config: {addr0}/{addr1}"
                )

            # price = (sqrtPriceX96 / 2^96)^2
            # This gives: canonical_token1 per canonical_token0 in raw units.
            # Adjust for decimals to get human-readable ratio.
            price_raw = (sqrt_price_x96 / (2 ** 96)) ** 2
            price = price_raw * (10 ** dec0) / (10 ** dec1)

            # If pair config is reversed, invert so result = token1 per token0
            if inverted:
                price = 1 / price if price else 0.0

            return price, None

        except Exception as e:
            return 0.0, str(e)

    # -----------------------------------------------------------------------
    # Backward-compat: old single-pool helper
    # -----------------------------------------------------------------------

    def get_uniswap_v3_spot_price(
        self,
        pool_address: str,
        token0_decimals: int = 18,
        token1_decimals: int = 8,
    ) -> float:
        """
        Decode sqrtPriceX96 directly (no address lookup).
        Returns canonical token1 per canonical token0 (adjusted for decimals).
        """
        pool = self.w3.eth.contract(
            address=Web3.to_checksum_address(pool_address),
            abi=UNISWAP_V3_POOL_ABI,
        )
        sqrt_price_x96 = pool.functions.slot0().call()[0]
        if sqrt_price_x96 == 0:
            return 0.0
        price_raw = (sqrt_price_x96 / (2 ** 96)) ** 2
        return price_raw * (10 ** token0_decimals) / (10 ** token1_decimals)

    def get_weth_wbtc_dex_price(self) -> float:
        """ETH price in BTC from the Uniswap V3 WETH/WBTC pool."""
        return self.get_uniswap_v3_spot_price(
            config.UNISWAP_WETH_WBTC_POOL,
            token0_decimals=18,
            token1_decimals=8,
        )
