"""
Core strategy analysis engine.
Combines price data, lending rates, and DEX prices to generate
investment strategy recommendations for the multisig wallet.
"""
import time
import uuid
from web3 import Web3

import config
from models.strategy import StrategyRecommendation, StrategyType, PriceSnapshot
from services.price_service   import PriceService
from services.lending_service import LendingService
from services.dex_service     import DexService

# Compound V3 supply ABI for calldata encoding
COMET_SUPPLY_ABI = [
    {
        "inputs": [
            {"name": "asset",  "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "supply",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

# Aave V3 supply ABI for calldata encoding
AAVE_SUPPLY_ABI = [
    {
        "inputs": [
            {"name": "asset",       "type": "address"},
            {"name": "amount",      "type": "uint256"},
            {"name": "onBehalfOf",  "type": "address"},
            {"name": "referralCode","type": "uint16"},
        ],
        "name": "supply",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

# Default suggestion: 1000 USDC (6 decimals)
_DEFAULT_USDC_AMOUNT = 1_000 * 10 ** 6
# Default suggestion: 0.1 WETH (18 decimals)
_DEFAULT_WETH_AMOUNT = int(0.1 * 10 ** 18)


class StrategyEngine:
    def __init__(self):
        self.w3       = Web3(Web3.HTTPProvider(config.RPC_URL))
        self.prices   = PriceService()
        self.lending  = LendingService()
        self.dex      = DexService()

    # -----------------------------------------------------------------------
    # Lending strategies
    # -----------------------------------------------------------------------

    def get_lending_opportunities(self) -> list[StrategyRecommendation]:
        snapshot  = self.prices.get_price_snapshot()
        best      = self.lending.get_best_lending_opportunity("USDC")
        apy       = best["apy"]

        if apy < config.LENDING_MIN_APY_PCT:
            return []

        # Encode calldata for the winning protocol
        if "Compound" in best["protocol"]:
            calldata = self._encode_compound_supply(
                best["asset"], _DEFAULT_USDC_AMOUNT
            )
            risk_score = 2
        else:
            calldata = self._encode_aave_supply(
                best["asset"], _DEFAULT_USDC_AMOUNT
            )
            risk_score = 3

        rec = StrategyRecommendation(
            id=f"lending-{best['protocol'].lower().replace(' ', '-')}-{int(time.time())}",
            strategy_type=StrategyType.LENDING,
            protocol_name=best["protocol"],
            protocol_address=Web3.to_checksum_address(best["protocol_address"]),
            description=(
                f"Supply {_DEFAULT_USDC_AMOUNT // 10**6} USDC to {best['protocol']} "
                f"at {apy:.2f}% APY"
            ),
            expected_return_pct=apy,
            risk_score=risk_score,
            token_in=Web3.to_checksum_address(best["asset"]),
            token_in_symbol=best["asset_symbol"],
            amount_suggestion_wei=str(_DEFAULT_USDC_AMOUNT),
            calldata=calldata,
            eth_value="0",
            price_snapshot=snapshot,
            expires_at=int(time.time()) + 300,  # valid 5 min
        )
        return [rec]

    # -----------------------------------------------------------------------
    # Arbitrage strategies
    # -----------------------------------------------------------------------

    def get_arbitrage_opportunities(self) -> list[StrategyRecommendation]:
        snapshot = self.prices.get_price_snapshot()

        try:
            dex_eth_btc = self.prices.get_weth_wbtc_dex_price()
        except Exception as e:
            print(f"[StrategyEngine] DEX price fetch failed: {e}")
            return []

        chainlink_eth_btc = snapshot.eth_btc_ratio
        if chainlink_eth_btc == 0 or dex_eth_btc == 0:
            return []

        spread_pct = self.dex.get_arbitrage_spread(chainlink_eth_btc, dex_eth_btc)
        abs_spread = abs(spread_pct)

        if abs_spread < config.ARBITRAGE_MIN_SPREAD_PCT:
            return []

        # Determine direction
        if spread_pct > 0:
            # DEX overprices ETH → sell WETH, buy WBTC on DEX
            token_in   = config.WETH
            token_out  = config.WBTC
            direction  = "Sell WETH → WBTC (ETH overpriced on DEX)"
            in_symbol  = "WETH"
            amount_in  = _DEFAULT_WETH_AMOUNT
        else:
            # DEX underprices ETH → buy WETH with WBTC on DEX
            token_in   = config.WBTC
            token_out  = config.WETH
            direction  = "Sell WBTC → WETH (ETH underpriced on DEX)"
            in_symbol  = "WBTC"
            amount_in  = int(0.001 * 10 ** 8)  # 0.001 WBTC

        # Estimate output and apply 0.5% slippage tolerance
        estimated_out = self.dex.estimate_swap_output(
            token_in, token_out, amount_in, fee=3000
        )
        min_out = int(estimated_out * 0.995) if estimated_out else 0

        calldata = self.dex.encode_swap_calldata(
            token_in=token_in,
            token_out=token_out,
            amount_in_wei=amount_in,
            amount_out_min_wei=min_out,
            recipient=config.CONTRACT_ADDRESS if config.CONTRACT_ADDRESS else "0x0000000000000000000000000000000000000001",
            fee=3000,
        )

        rec = StrategyRecommendation(
            id=f"arbitrage-weth-wbtc-{int(time.time())}",
            strategy_type=StrategyType.ARBITRAGE,
            protocol_name="Uniswap V3",
            protocol_address=Web3.to_checksum_address(config.UNISWAP_V3_ROUTER),
            description=(
                f"{direction} | Chainlink ETH/BTC: {chainlink_eth_btc:.6f} | "
                f"DEX ETH/BTC: {dex_eth_btc:.6f} | Spread: {abs_spread:.3f}%"
            ),
            expected_return_pct=round(abs_spread, 3),
            risk_score=6,
            token_in=Web3.to_checksum_address(token_in),
            token_in_symbol=in_symbol,
            amount_suggestion_wei=str(amount_in),
            calldata=calldata,
            eth_value="0",
            price_snapshot=snapshot,
            expires_at=int(time.time()) + 60,   # arbitrage window short: 1 min
        )
        return [rec]

    # -----------------------------------------------------------------------
    # All opportunities
    # -----------------------------------------------------------------------

    def get_all_opportunities(self) -> dict:
        lending   = self.get_lending_opportunities()
        arbitrage = self.get_arbitrage_opportunities()
        return {
            "lending":      lending,
            "arbitrage":    arbitrage,
            "generated_at": int(time.time()),
        }

    # -----------------------------------------------------------------------
    # Calldata encoding helpers
    # -----------------------------------------------------------------------

    def _encode_compound_supply(self, asset: str, amount: int) -> str:
        comet = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.COMPOUND_V3_USDC),
            abi=COMET_SUPPLY_ABI,
        )
        return comet.encodeABI(
            fn_name="supply",
            args=[Web3.to_checksum_address(asset), amount],
        )

    def _encode_aave_supply(self, asset: str, amount: int) -> str:
        pool = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.AAVE_V3_POOL),
            abi=AAVE_SUPPLY_ABI,
        )
        on_behalf_of = (
            Web3.to_checksum_address(config.CONTRACT_ADDRESS)
            if config.CONTRACT_ADDRESS
            else "0x0000000000000000000000000000000000000001"
        )
        return pool.encodeABI(
            fn_name="supply",
            args=[Web3.to_checksum_address(asset), amount, on_behalf_of, 0],
        )
