from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.price_service import PriceService

router = APIRouter(prefix="/api/prices", tags=["prices"])
_svc = PriceService()


class PricesResponse(BaseModel):
    eth_usd: float
    btc_usd: float
    eth_btc_ratio: float
    updated_at: int
    is_fresh: bool


@router.get("", response_model=PricesResponse)
def get_prices():
    """Return latest ETH/USD and BTC/USD prices from Chainlink."""
    try:
        snap = _svc.get_price_snapshot()
        return PricesResponse(
            eth_usd=snap.eth_usd,
            btc_usd=snap.btc_usd,
            eth_btc_ratio=snap.eth_btc_ratio,
            updated_at=snap.updated_at,
            is_fresh=snap.is_fresh,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
