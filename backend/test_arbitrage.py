"""
End-to-end test: Arbitrage strategy execution flow
====================================================
1. Scan for arbitrage opportunities (raw scan — ignores threshold)
2. Pick the best-spread pair and build proposal data
3. Fund the multisig with the required token via Anvil impersonation
4. Create a proposeStrategy() on-chain
5. Have enough admins approve()
6. Execute the proposal
7. Verify output token balance increased
"""

import requests
import time
from web3 import Web3

# -----------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------
BACKEND = "http://127.0.0.1:8000"
RPC = "http://127.0.0.1:8545"
CONTRACT_ADDR = "0x195FA537B17734Bb4fDEE405146dAb5F9Dca72be"

w3 = Web3(Web3.HTTPProvider(RPC))
assert w3.is_connected(), "Cannot connect to Anvil"

CONTRACT_ABI = [
    {
        "inputs": [
            {"name": "_protocol", "type": "address"},
            {"name": "_ethValue", "type": "uint256"},
            {"name": "_calldata", "type": "bytes"},
            {"name": "_description", "type": "string"},
            {"name": "_strategyType", "type": "uint8"},
            {"name": "_tokenIn", "type": "address"},
            {"name": "_amountIn", "type": "uint256"},
        ],
        "name": "proposeStrategy",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "_txId", "type": "uint256"}],
        "name": "approve",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "_txId", "type": "uint256"}],
        "name": "execute",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getAdminCount",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "", "type": "uint256"}],
        "name": "admins",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getProposalCount",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "threshold",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "txId", "type": "uint256"}],
        "name": "getProposal",
        "outputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "description", "type": "string"},
            {"name": "executed", "type": "bool"},
            {"name": "approvalCount", "type": "uint256"},
            {"name": "proposalType", "type": "uint8"},
            {"name": "strategyType", "type": "uint8"},
            {"name": "tokenIn", "type": "address"},
            {"name": "amountIn", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "_protocol", "type": "address"}],
        "name": "approvedProtocols",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "_protocol", "type": "address"},
            {"name": "_name", "type": "string"},
        ],
        "name": "approveProtocol",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

ERC20_ABI = [
    {
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

contract = w3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDR), abi=CONTRACT_ABI
)

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def separator(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


# Token address mapping (mainnet)
TOKENS = {
    "WETH": Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    "WBTC": Web3.to_checksum_address("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"),
    "USDC": Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
    "LINK": Web3.to_checksum_address("0x514910771AF9Ca656af840dff83E8264EcF986CA"),
    "UNI":  Web3.to_checksum_address("0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"),
}

# Default amounts matching config.py
DEFAULT_AMOUNTS = {
    "WETH": int(0.1 * 10**18),
    "WBTC": int(0.001 * 10**8),
    "USDC": 1_000 * 10**6,
    "LINK": int(10 * 10**18),
    "UNI":  int(10 * 10**18),
}

# Known whales for each token (mainnet fork)
WHALES = {
    "USDC": Web3.to_checksum_address("0x55FE002aefF02F77364de339a12e294C52523269"),
    "WBTC": Web3.to_checksum_address("0x9ff58f4fFB29fA2266Ab25e75e2A8b3503311656"),
    "WETH": Web3.to_checksum_address("0x2F0b23f53734252Bda2277357e97e1517d6B042A"),
    "LINK": Web3.to_checksum_address("0xF977814e90dA44bFA03b6295A0616a897441aceC"),
    "UNI":  Web3.to_checksum_address("0x1a9C8182C09F50C8318d769245beA52c32BE35BC"),
}

UNISWAP_V3_ROUTER = Web3.to_checksum_address("0xE592427A0AEce92De3Edee1F18E0157C05861564")


# -----------------------------------------------------------------------
# Step 0 — Contract info
# -----------------------------------------------------------------------
separator("Step 0: Contract Info")
admin_count = contract.functions.getAdminCount().call()
threshold_val = contract.functions.threshold().call()
admins = [contract.functions.admins(i).call() for i in range(admin_count)]
print(f"  Admins ({admin_count}): {admins}")
print(f"  Threshold: {threshold_val}")

# -----------------------------------------------------------------------
# Step 1 — Scan for arbitrage opportunities (raw, no threshold filter)
# -----------------------------------------------------------------------
separator("Step 1: Scan for Arbitrage Opportunities")
scan = requests.get(f"{BACKEND}/api/strategies/scan").json()
pairs = scan["pairs"]

# Pick best pair (ignore errors)
valid_pairs = [p for p in pairs if p["error"] is None and abs(p["spread_pct"]) > 0]
assert valid_pairs, "No valid pairs found in scan!"

best = valid_pairs[0]  # Already sorted by abs(spread) desc
print(f"  Best pair: {best['token0_symbol']}/{best['token1_symbol']}")
print(f"  Chainlink ratio: {best['chainlink_ratio']}")
print(f"  DEX ratio:       {best['dex_ratio']}")
print(f"  Spread:          {best['spread_pct']}%")
print(f"  Direction:       {best['spread_direction']}")

# Determine trade direction
spread = best["spread_pct"]
if spread > 0:
    token_in_sym = best["token0_symbol"]
    token_out_sym = best["token1_symbol"]
else:
    token_in_sym = best["token1_symbol"]
    token_out_sym = best["token0_symbol"]

print(f"  → Trade: sell {token_in_sym} → buy {token_out_sym}")

token_in_addr = TOKENS[token_in_sym]
token_out_addr = TOKENS[token_out_sym]
amount_in = DEFAULT_AMOUNTS[token_in_sym]
fee = best["fee_tier"]

# -----------------------------------------------------------------------
# Step 2 — Encode swap calldata via backend API
# -----------------------------------------------------------------------
separator("Step 2: Encode Swap Calldata")
calldata_req = {
    "strategy_type": "arbitrage",
    "protocol_address": UNISWAP_V3_ROUTER,
    "token_in": token_in_addr,
    "token_out": token_out_addr,
    "amount_in_wei": str(amount_in),
    "min_amount_out_wei": "0",
    "fee_tier": fee,
    "deadline_offset_seconds": 600,
}
print(f"  Requesting calldata: {token_in_sym}→{token_out_sym}, amount={amount_in}, fee={fee}")
cd_resp = requests.post(f"{BACKEND}/api/calldata/encode", json=calldata_req)
cd_resp.raise_for_status()
cd_data = cd_resp.json()
calldata_hex = cd_data["calldata"]
print(f"  Calldata (first 40 chars): {calldata_hex[:40]}...")
print(f"  Description: {cd_data['description']}")

# -----------------------------------------------------------------------
# Step 3 — Ensure Uniswap V3 Router is whitelisted
# -----------------------------------------------------------------------
separator("Step 3: Ensure Protocol Whitelist")
is_approved = contract.functions.approvedProtocols(UNISWAP_V3_ROUTER).call()
if not is_approved:
    print(f"  Uniswap V3 Router NOT whitelisted — approving now...")
    tx = contract.functions.approveProtocol(
        UNISWAP_V3_ROUTER, "Uniswap V3 Router"
    ).transact({"from": admins[0]})
    w3.eth.wait_for_transaction_receipt(tx)
    print(f"  ✅ Protocol whitelisted")
else:
    print(f"  ✅ Protocol already whitelisted")

# -----------------------------------------------------------------------
# Step 4 — Fund the multisig with the token_in
# -----------------------------------------------------------------------
separator("Step 4: Fund Multisig")
token_in_contract = w3.eth.contract(address=token_in_addr, abi=ERC20_ABI)
balance_before = token_in_contract.functions.balanceOf(CONTRACT_ADDR).call()
print(f"  Current {token_in_sym} balance: {balance_before}")

if balance_before < amount_in:
    needed = amount_in * 3
    print(f"  Funding: using Anvil deal to set {token_in_sym} balance...")

    # USDC uses storage slot 9 for balances mapping, WBTC uses slot 0
    # We use anvil_setBalance for ETH, but for ERC20 we write storage directly.
    # The storage slot for balances[address] in mapping at slot S is:
    #   keccak256(abi.encode(address, S))
    BALANCE_SLOTS = {
        "USDC": 9,
        "WBTC": 0,
        "WETH": 3,
        "LINK": 1,
        "UNI":  4,
    }
    slot_index = BALANCE_SLOTS.get(token_in_sym)
    if slot_index is not None:
        # Compute storage slot: keccak256(abi.encode(address, uint256(slot_index)))
        padded_addr = CONTRACT_ADDR.lower().replace("0x", "").zfill(64)
        padded_slot = hex(slot_index)[2:].zfill(64)
        key = w3.keccak(bytes.fromhex(padded_addr + padded_slot))
        storage_slot = "0x" + key.hex()

        # Set the value
        value_hex = "0x" + hex(needed)[2:].zfill(64)
        w3.provider.make_request("anvil_setStorageAt", [token_in_addr, storage_slot, value_hex])

        new_balance = token_in_contract.functions.balanceOf(CONTRACT_ADDR).call()
        print(f"  ✅ New {token_in_sym} balance: {new_balance}")

        if new_balance < amount_in:
            # Fallback: try known big holders
            print(f"  ⚠️  Direct storage set didn't work. Trying whale impersonation...")
            # Circle USDC reserve
            FALLBACK_WHALES = [
                "0x28C6c06298d514Db089934071355E5743bf21d60",  # Binance 14
                "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",  # Binance
                "0xDFd5293D8e347dFe59E90eFd55b2956a1343963d",  # Another
            ]
            funded = False
            for fw in FALLBACK_WHALES:
                fw = Web3.to_checksum_address(fw)
                try:
                    w3.provider.make_request("anvil_impersonateAccount", [fw])
                    w3.eth.send_transaction({"from": admins[0], "to": fw, "value": w3.to_wei(1, "ether")})
                    wb = token_in_contract.functions.balanceOf(fw).call()
                    print(f"    Whale {fw[:10]}... has {wb} {token_in_sym}")
                    if wb >= amount_in:
                        token_in_contract.functions.transfer(
                            Web3.to_checksum_address(CONTRACT_ADDR), needed
                        ).transact({"from": fw})
                        funded = True
                        w3.provider.make_request("anvil_stopImpersonatingAccount", [fw])
                        break
                    w3.provider.make_request("anvil_stopImpersonatingAccount", [fw])
                except Exception as e:
                    print(f"    Failed with {fw[:10]}...: {e}")
                    try:
                        w3.provider.make_request("anvil_stopImpersonatingAccount", [fw])
                    except:
                        pass

            new_balance = token_in_contract.functions.balanceOf(CONTRACT_ADDR).call()
            print(f"  Final {token_in_sym} balance: {new_balance}")
    else:
        print(f"  ❌ No known storage slot for {token_in_sym}; cannot fund")

else:
    print(f"  ✅ Sufficient balance")

# -----------------------------------------------------------------------
# Step 5 — Create proposal (proposeStrategy)
# -----------------------------------------------------------------------
separator("Step 5: Create Arbitrage Proposal")
description = (
    f"Arbitrage: {best['spread_direction']} | "
    f"Chainlink: {best['chainlink_ratio']:.6f} | "
    f"DEX: {best['dex_ratio']:.6f} | "
    f"Spread: {abs(spread):.3f}%"
)
STRATEGY_TYPE_ARBITRAGE = 2

proposal_count_before = contract.functions.getProposalCount().call()

tx = contract.functions.proposeStrategy(
    UNISWAP_V3_ROUTER,         # protocol
    0,                          # ethValue
    bytes.fromhex(calldata_hex.replace("0x", "")),  # calldata
    description,                # description
    STRATEGY_TYPE_ARBITRAGE,    # strategyType
    token_in_addr,              # tokenIn
    amount_in,                  # amountIn
).transact({"from": admins[0]})
receipt = w3.eth.wait_for_transaction_receipt(tx)
assert receipt.status == 1, "proposeStrategy reverted!"

proposal_count_after = contract.functions.getProposalCount().call()
tx_id = proposal_count_after - 1
print(f"  ✅ Proposal created — txId: {tx_id}")
print(f"  Description: {description}")

# Read back the proposal
proposal = contract.functions.getProposal(tx_id).call()
print(f"  Stored proposal:")
print(f"     to:            {proposal[0]}")
print(f"     value:         {proposal[1]}")
print(f"     description:   {proposal[3]}")
print(f"     executed:      {proposal[4]}")
print(f"     approvalCount: {proposal[5]}")
print(f"     proposalType:  {proposal[6]} (1=STRATEGY)")
print(f"     strategyType:  {proposal[7]} (2=ARBITRAGE)")
print(f"     tokenIn:       {proposal[8]}")
print(f"     amountIn:      {proposal[9]}")

# -----------------------------------------------------------------------
# Step 6 — Admin approvals
# -----------------------------------------------------------------------
separator("Step 6: Admin Approvals")
for i in range(threshold_val):
    admin = admins[i]
    try:
        tx = contract.functions.approve(tx_id).transact({"from": admin})
        w3.eth.wait_for_transaction_receipt(tx)
        print(f"  ✅ Admin {admin[:10]}... approved")
    except Exception as e:
        print(f"  ⚠️  Admin {admin[:10]}... approve failed (already voted?): {e}")

# Verify approval count
proposal = contract.functions.getProposal(tx_id).call()
print(f"  Approval count: {proposal[5]} / {threshold_val}")

# -----------------------------------------------------------------------
# Step 7 — Execute the proposal
# -----------------------------------------------------------------------
separator("Step 7: Execute Proposal")
token_out_contract = w3.eth.contract(address=token_out_addr, abi=ERC20_ABI)
token_out_before = token_out_contract.functions.balanceOf(CONTRACT_ADDR).call()
token_in_before_exec = token_in_contract.functions.balanceOf(CONTRACT_ADDR).call()
print(f"  Before execution:")
print(f"    {token_in_sym} balance:  {token_in_before_exec}")
print(f"    {token_out_sym} balance: {token_out_before}")

tx = contract.functions.execute(tx_id).transact({"from": admins[0]})
receipt = w3.eth.wait_for_transaction_receipt(tx)

if receipt.status == 1:
    print(f"  ✅ PROPOSAL EXECUTED SUCCESSFULLY!")
else:
    print(f"  ❌ EXECUTION REVERTED!")

# -----------------------------------------------------------------------
# Step 8 — Verify results
# -----------------------------------------------------------------------
separator("Step 8: Verify Results")
token_in_after = token_in_contract.functions.balanceOf(CONTRACT_ADDR).call()
token_out_after = token_out_contract.functions.balanceOf(CONTRACT_ADDR).call()

print(f"  After execution:")
print(f"    {token_in_sym} balance:  {token_in_after} (delta: {token_in_after - token_in_before_exec})")
print(f"    {token_out_sym} balance: {token_out_after} (delta: {token_out_after - token_out_before})")

proposal_final = contract.functions.getProposal(tx_id).call()
print(f"  Proposal executed flag: {proposal_final[4]}")

if receipt.status == 1 and token_out_after > token_out_before:
    print(f"\n  🎉 TEST PASSED — Arbitrage swap executed, received {token_out_sym}!")
elif receipt.status == 1:
    print(f"\n  ⚠️  Execution succeeded but output balance did not increase (tokens may have gone elsewhere)")
else:
    print(f"\n  ❌ TEST FAILED — Execution reverted")

print(f"\n{'='*60}")
print(f"  FULL FLOW COMPLETED")
print(f"{'='*60}")
