"""
Queries DEX pool prices and estimates arbitrage spreads.
Uses Uniswap V3 pool slot0 to read on-chain prices.
"""
from web3 import Web3

import config

# Uniswap V3 Quoter ABI (quoterV2 – read-only simulation)
QUOTER_V2_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn",            "type": "address"},
                    {"name": "tokenOut",           "type": "address"},
                    {"name": "amountIn",           "type": "uint256"},
                    {"name": "fee",                "type": "uint24"},
                    {"name": "sqrtPriceLimitX96",  "type": "uint160"},
                ],
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"name": "amountOut",           "type": "uint256"},
            {"name": "sqrtPriceX96After",   "type": "uint160"},
            {"name": "initializedTicksCrossed", "type": "uint32"},
            {"name": "gasEstimate",         "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Uniswap V3 QuoterV2 address (mainnet & Sepolia)
UNISWAP_QUOTER_V2 = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"


class DexService:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
        self._quoter = self.w3.eth.contract(
            address=Web3.to_checksum_address(UNISWAP_QUOTER_V2),
            abi=QUOTER_V2_ABI,
        )

    def estimate_swap_output(
        self,
        token_in: str,
        token_out: str,
        amount_in_wei: int,
        fee: int = 3000,
    ) -> int:
        """
        Use Uniswap V3 QuoterV2 to estimate output amount for a swap.
        Returns amountOut in token_out's smallest unit.
        """
        try:
            result = self._quoter.functions.quoteExactInputSingle({
                "tokenIn":           Web3.to_checksum_address(token_in),
                "tokenOut":          Web3.to_checksum_address(token_out),
                "amountIn":          amount_in_wei,
                "fee":               fee,
                "sqrtPriceLimitX96": 0,
            }).call()
            return result[0]  # amountOut
        except Exception as e:
            print(f"[DexService] QuoterV2 error: {e}")
            return 0

    def encode_swap_calldata(
        self,
        token_in: str,
        token_out: str,
        amount_in_wei: int,
        amount_out_min_wei: int,
        recipient: str,
        fee: int = 3000,
        deadline_offset: int = 300,
    ) -> str:
        """
        Encode Uniswap V3 exactInputSingle calldata.
        Returns 0x-prefixed hex string.
        """
        from web3 import Web3

        # ISwapRouter.exactInputSingle ABI
        router_abi = [
            {
                "inputs": [
                    {
                        "components": [
                            {"name": "tokenIn",            "type": "address"},
                            {"name": "tokenOut",           "type": "address"},
                            {"name": "fee",                "type": "uint24"},
                            {"name": "recipient",          "type": "address"},
                            {"name": "deadline",           "type": "uint256"},
                            {"name": "amountIn",           "type": "uint256"},
                            {"name": "amountOutMinimum",   "type": "uint256"},
                            {"name": "sqrtPriceLimitX96",  "type": "uint160"},
                        ],
                        "name": "params",
                        "type": "tuple",
                    }
                ],
                "name": "exactInputSingle",
                "outputs": [{"name": "amountOut", "type": "uint256"}],
                "stateMutability": "payable",
                "type": "function",
            }
        ]
        router = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.UNISWAP_V3_ROUTER),
            abi=router_abi,
        )

        # Use the current block timestamp as deadline base
        try:
            current_ts = self.w3.eth.get_block("latest")["timestamp"]
        except Exception:
            import time
            current_ts = int(time.time())

        params = {
            "tokenIn":           Web3.to_checksum_address(token_in),
            "tokenOut":          Web3.to_checksum_address(token_out),
            "fee":               fee,
            "recipient":         Web3.to_checksum_address(recipient),
            "deadline":          current_ts + deadline_offset,
            "amountIn":          amount_in_wei,
            "amountOutMinimum":  amount_out_min_wei,
            "sqrtPriceLimitX96": 0,
        }
        calldata = router.encode_abi(abi_element_identifier="exactInputSingle", args=[params])
        return calldata
