"""
Core strategy analysis engine.
Combines price data, lending rates, and DEX prices to generate
investment strategy recommendations for the multisig wallet.
"""
import time
from web3 import Web3

import config
from models.strategy import (
    PairScanResult,
    PairScanResponse,
    StrategyRecommendation,
    StrategyType,
    PriceSnapshot,
)
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
        snapshot = self.prices.get_price_snapshot()
        best     = self.lending.get_best_lending_opportunity("USDC")
        apy      = best["apy"]

        if apy < config.LENDING_MIN_APY_PCT:
            return []

        if "Compound" in best["protocol"]:
            calldata   = self._encode_compound_supply(best["asset"], _DEFAULT_USDC_AMOUNT)
            risk_score = 2
        else:
            calldata   = self._encode_aave_supply(best["asset"], _DEFAULT_USDC_AMOUNT)
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
            expires_at=int(time.time()) + 300,
        )
        return [rec]

    # -----------------------------------------------------------------------
    # Multi-pair arbitrage scanner
    # -----------------------------------------------------------------------

    def scan_all_pairs(self) -> PairScanResponse:
        """
        Scan every pair in config.ARBITRAGE_PAIRS.
        Fetches all token USD prices once, then computes per-pair spreads.
        Returns a PairScanResponse with all results sorted by abs(spread) desc.
        """
        token_prices = self.prices.get_all_token_prices()
        results: list[PairScanResult] = []

        for pair in config.ARBITRAGE_PAIRS:
            sym0 = pair["token0"]
            sym1 = pair["token1"]
            pool = pair["pool_address"]
            fee  = pair["fee"]

            price0 = token_prices.get(sym0)
            price1 = token_prices.get(sym1)

            if not price0 or not price1:
                results.append(PairScanResult(
                    token0_symbol=sym0,
                    token1_symbol=sym1,
                    pool_address=pool,
                    fee_tier=fee,
                    chainlink_ratio=0.0,
                    dex_ratio=0.0,
                    spread_pct=0.0,
                    spread_direction="",
                    above_threshold=False,
                    error=f"Missing Chainlink price for {sym0 if not price0 else sym1}",
                ))
                continue

            # chainlink_ratio: how many token1 you should get per token0
            chainlink_ratio = price0 / price1

            dex_ratio, err = self.prices.get_pool_price_ratio(pair)
            if err or dex_ratio == 0:
                results.append(PairScanResult(
                    token0_symbol=sym0,
                    token1_symbol=sym1,
                    pool_address=pool,
                    fee_tier=fee,
                    chainlink_ratio=round(chainlink_ratio, 8),
                    dex_ratio=0.0,
                    spread_pct=0.0,
                    spread_direction="",
                    above_threshold=False,
                    error=err or "DEX price is 0",
                ))
                continue

            # spread > 0: DEX gives more token1 than Chainlink expects → sell token0 on DEX
            # spread < 0: DEX gives fewer token1 → sell token1 on DEX (buy token0)
            spread_pct = (dex_ratio - chainlink_ratio) / chainlink_ratio * 100

            if spread_pct > 0:
                direction = f"Sell {sym0}→{sym1} (DEX overprices {sym0})"
            else:
                direction = f"Sell {sym1}→{sym0} (DEX underprices {sym0})"

            results.append(PairScanResult(
                token0_symbol=sym0,
                token1_symbol=sym1,
                pool_address=pool,
                fee_tier=fee,
                chainlink_ratio=round(chainlink_ratio, 8),
                dex_ratio=round(dex_ratio, 8),
                spread_pct=round(spread_pct, 4),
                spread_direction=direction,
                above_threshold=abs(spread_pct) >= config.ARBITRAGE_MIN_SPREAD_PCT,
                error=None,
            ))

        # Sort by absolute spread descending
        results.sort(key=lambda r: abs(r.spread_pct), reverse=True)
        best = max((abs(r.spread_pct) for r in results if r.error is None), default=0.0)

        return PairScanResponse(
            pairs=results,
            best_spread_pct=round(best, 4),
            generated_at=int(time.time()),
        )

    def get_arbitrage_opportunities(self) -> list[StrategyRecommendation]:
        """
        Scan all pairs and convert those above the spread threshold into
        StrategyRecommendation objects, sorted best-spread first.
        """
        scan     = self.scan_all_pairs()
        snapshot = self.prices.get_price_snapshot()
        recs: list[StrategyRecommendation] = []

        for result in scan.pairs:
            if not result.above_threshold or result.error:
                continue

            sym0   = result.token0_symbol
            sym1   = result.token1_symbol
            meta0  = config.TOKENS.get(sym0, {})
            meta1  = config.TOKENS.get(sym1, {})

            spread = result.spread_pct

            if spread > 0:
                # DEX over-prices token0 → sell token0, receive token1
                token_in_sym  = sym0
                token_out_sym = sym1
            else:
                token_in_sym  = sym1
                token_out_sym = sym0

            meta_in  = config.TOKENS.get(token_in_sym, {})
            meta_out = config.TOKENS.get(token_out_sym, {})

            token_in_addr  = meta_in.get("address", "")
            token_out_addr = meta_out.get("address", "")
            amount_in      = meta_in.get("default_amount", 0)
            fee            = result.fee_tier

            if not token_in_addr or not token_out_addr or not amount_in:
                continue

            estimated_out = self.dex.estimate_swap_output(
                token_in_addr, token_out_addr, amount_in, fee=fee
            )
            min_out = int(estimated_out * 0.995) if estimated_out else 0

            recipient = (
                Web3.to_checksum_address(config.CONTRACT_ADDRESS)
                if config.CONTRACT_ADDRESS
                else "0x0000000000000000000000000000000000000001"
            )

            calldata = self.dex.encode_swap_calldata(
                token_in=token_in_addr,
                token_out=token_out_addr,
                amount_in_wei=amount_in,
                amount_out_min_wei=min_out,
                recipient=recipient,
                fee=fee,
            )

            recs.append(StrategyRecommendation(
                id=f"arbitrage-{token_in_sym.lower()}-{token_out_sym.lower()}-{int(time.time())}",
                strategy_type=StrategyType.ARBITRAGE,
                protocol_name="Uniswap V3",
                protocol_address=Web3.to_checksum_address(config.UNISWAP_V3_ROUTER),
                description=(
                    f"{result.spread_direction} | "
                    f"Chainlink: {result.chainlink_ratio:.6f} | "
                    f"DEX: {result.dex_ratio:.6f} | "
                    f"Spread: {abs(spread):.3f}%"
                ),
                expected_return_pct=round(abs(spread), 3),
                risk_score=6,
                token_in=Web3.to_checksum_address(token_in_addr),
                token_in_symbol=token_in_sym,
                amount_suggestion_wei=str(amount_in),
                calldata=calldata,
                eth_value="0",
                price_snapshot=snapshot,
                expires_at=int(time.time()) + 60,   # arbitrage window: 1 min
            ))

        return recs

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
