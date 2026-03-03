from fastapi import APIRouter, HTTPException
from web3 import Web3

import config
from models.strategy import CalldataRequest, CalldataResponse, StrategyType
from services.strategy_engine import StrategyEngine
from services.dex_service     import DexService

router  = APIRouter(prefix="/api/calldata", tags=["calldata"])
_engine = StrategyEngine()
_dex    = DexService()


@router.post("/encode", response_model=CalldataResponse)
def encode_calldata(req: CalldataRequest):
    """
    Generate ABI-encoded calldata for a strategy proposal.
    The frontend sends this calldata along with the protocol address
    when calling proposeStrategy() on the smart contract.
    """
    try:
        if req.strategy_type == StrategyType.LENDING:
            amount = int(req.amount_in_wei)
            asset  = req.token_in

            if config.COMPOUND_V3_USDC.lower() == req.protocol_address.lower():
                calldata    = _engine._encode_compound_supply(asset, amount)
                description = f"Supply {amount} to Compound V3"
                eth_value   = "0"
            elif config.AAVE_V3_POOL.lower() == req.protocol_address.lower():
                calldata    = _engine._encode_aave_supply(asset, amount)
                description = f"Supply {amount} to Aave V3"
                eth_value   = "0"
            else:
                raise HTTPException(status_code=400, detail="Unknown lending protocol")

        elif req.strategy_type == StrategyType.ARBITRAGE:
            if not req.token_out:
                raise HTTPException(status_code=400, detail="token_out required for arbitrage")

            amount_in  = int(req.amount_in_wei)
            min_out    = int(req.min_amount_out_wei or "0")
            fee        = req.fee_tier or 3000
            deadline   = req.deadline_offset_seconds or 300
            recipient  = (
                Web3.to_checksum_address(config.CONTRACT_ADDRESS)
                if config.CONTRACT_ADDRESS
                else "0x0000000000000000000000000000000000000001"
            )

            calldata = _dex.encode_swap_calldata(
                token_in=req.token_in,
                token_out=req.token_out,
                amount_in_wei=amount_in,
                amount_out_min_wei=min_out,
                recipient=recipient,
                fee=fee,
                deadline_offset=deadline,
            )
            description = (
                f"Swap {amount_in} of {req.token_in} → {req.token_out} "
                f"on Uniswap V3 (fee={fee})"
            )
            eth_value = "0"

        else:
            raise HTTPException(status_code=400, detail="Unsupported strategy type")

        return CalldataResponse(
            calldata=calldata,
            eth_value=eth_value,
            description=description,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
