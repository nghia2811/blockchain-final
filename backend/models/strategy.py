"""
Pydantic data models for strategy recommendations and price data.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class StrategyType(str, Enum):
    LENDING   = "lending"
    ARBITRAGE = "arbitrage"


class PriceSnapshot(BaseModel):
    eth_usd: float
    btc_usd: float
    eth_btc_ratio: float
    updated_at: int                    # unix timestamp of Chainlink answer
    is_fresh: bool
    token_prices: dict[str, float] = {}  # symbol → USD price for all scanned tokens


class PairScanResult(BaseModel):
    """Raw scan result for a single token pair — returned by /api/strategies/scan."""
    token0_symbol: str
    token1_symbol: str
    pool_address: str
    fee_tier: int
    chainlink_ratio: float             # token0_usd / token1_usd (expected DEX price)
    dex_ratio: float                   # actual DEX price (token1 per token0)
    spread_pct: float                  # (chainlink - dex) / chainlink * 100
    spread_direction: str              # e.g. "Sell WETH→USDC" or "Sell USDC→WETH"
    above_threshold: bool
    error: Optional[str] = None        # set if the scan for this pair failed


class PairScanResponse(BaseModel):
    pairs: list[PairScanResult]
    best_spread_pct: float             # abs spread of the most attractive pair
    generated_at: int


class StrategyRecommendation(BaseModel):
    id: str                            # unique identifier (e.g. "lending-compound-usdc-1234")
    strategy_type: StrategyType
    protocol_name: str                 # e.g. "Compound V3 USDC"
    protocol_address: str              # checksum address
    description: str                   # human-readable summary
    expected_return_pct: float         # estimated annualised return %
    risk_score: int                    # 1 (low) – 10 (high)
    token_in: str                      # checksum token address or "ETH"
    token_in_symbol: str               # e.g. "USDC", "WETH"
    amount_suggestion_wei: str         # suggested input amount as integer string (wei)
    calldata: str                      # 0x-prefixed hex calldata for the contract call
    eth_value: str                     # ETH to forward as integer string (wei); "0" for ERC20
    price_snapshot: PriceSnapshot
    expires_at: int                    # unix timestamp after which recs should be refreshed


class OpportunitiesResponse(BaseModel):
    lending: list[StrategyRecommendation]
    arbitrage: list[StrategyRecommendation]
    generated_at: int                  # unix timestamp


class CalldataRequest(BaseModel):
    strategy_type: StrategyType
    protocol_address: str
    token_in: str                      # address or "ETH"
    amount_in_wei: str                 # integer string
    # Arbitrage-specific
    token_out: Optional[str] = None
    fee_tier: Optional[int]  = 3000    # Uniswap fee tier (500 / 3000 / 10000)
    min_amount_out_wei: Optional[str] = "0"
    deadline_offset_seconds: Optional[int] = 300


class CalldataResponse(BaseModel):
    calldata: str                      # 0x hex
    eth_value: str                     # wei as integer string
    description: str
