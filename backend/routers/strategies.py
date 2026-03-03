from fastapi import APIRouter, HTTPException

from models.strategy import StrategyRecommendation, OpportunitiesResponse
from services.strategy_engine import StrategyEngine

router = APIRouter(prefix="/api/strategies", tags=["strategies"])
_engine = StrategyEngine()


@router.get("/opportunities", response_model=OpportunitiesResponse)
def get_all_opportunities():
    """Return all current lending and arbitrage opportunities."""
    try:
        result = _engine.get_all_opportunities()
        return OpportunitiesResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/lending", response_model=list[StrategyRecommendation])
def get_lending():
    """Return lending strategy recommendations."""
    try:
        return _engine.get_lending_opportunities()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/arbitrage", response_model=list[StrategyRecommendation])
def get_arbitrage():
    """Return arbitrage strategy recommendations."""
    try:
        return _engine.get_arbitrage_opportunities()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
