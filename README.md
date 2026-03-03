# Group Multisig Asset Manager

A decentralized application (DApp) for group fund management combining **multi-signature security** with an **AI-powered investment strategy engine** backed by on-chain Chainlink price feeds.

---

## Features

- **Multi-Signature Wallet** — Secure fund management requiring *threshold-of-N* admin approvals before any transaction executes
- **Proposal System** — Create, approve, and execute fund transfer or investment proposals
- **Investment Strategy Engine** — Python backend analyses live Chainlink prices and on-chain lending rates; generates ready-to-execute lending and arbitrage proposals
- **Multi-Pair Arbitrage Scanner** — Dynamically scans all configured token pairs (WETH/USDC, WETH/WBTC, WBTC/USDC, LINK/WETH, UNI/WETH) and ranks them by spread — no hardcoded pairs
- **Protocol Whitelist** — Only pre-approved external protocols (Uniswap V3, Compound V3, Aave V3, …) can be called by the contract
- **Chainlink Integration** — On-chain price feeds for ETH, BTC, USDC, LINK, UNI; frontend displays live ticker
- **Web Interface** — Dashboard with strategy recommendations, proposal management, and transaction history

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        FRONTEND                         │
│  (web_app/index.html + script.js + ethers.js v5)        │
│                                                         │
│  ① Price Ticker          ② Strategy Cards              │
│     ETH/USD, BTC/USD        Lending APY, Arbitrage      │
│     (polled every 30s)      spread, expected return     │
│                             [Create Proposal ↓]         │
└────────────┬────────────────────────┬───────────────────┘
             │  HTTP REST             │  ethers.js
             │  /api/prices           │  proposeStrategy()
             │  /api/strategies       │  approve() / execute()
             │  /api/strategies/scan  │
             ▼                        ▼
┌────────────────────┐   ┌────────────────────────────────┐
│   PYTHON BACKEND   │   │       SMART CONTRACT           │
│   FastAPI :8000    │   │  MultisigWalletWithStrategies  │
│                    │   │                                │
│ PriceService       │   │  • Protocol whitelist          │
│  └─ Chainlink      │   │  • Chainlink price feeds       │
│     (all tokens)   │   │  • proposeStrategy()           │
│                    │   │  • approve() / execute()       │
│ LendingService     │   │  • _executeStrategy()          │
│  └─ Compound APY   │   │    └─ ERC20.approve()          │
│  └─ Aave APY       │   │    └─ protocol.call(calldata)  │
│                    │   └───────────────┬────────────────┘
│ DexService         │                   │ call(calldata)
│  └─ Uniswap slot0  │                   ▼
│  └─ QuoterV2       │   ┌──────────────────────────────┐
│                    │   │  EXTERNAL PROTOCOLS          │
│ StrategyEngine     │   │  • Compound V3 (lending)     │
│  └─ multi-pair scan│   │  • Aave V3 (lending)         │
│  └─ encode calldata│   │  • Uniswap V3 (arbitrage)    │
│  └─ StrategyRec    │──▶│                              │
└────────────────────┘   └──────────────────────────────┘
```

---

## Complete Flow

### Flow 1 — Transfer (standard multisig)

```
Admin A                  Admin B                  Contract
   │                        │                        │
   │── propose(to, ETH) ───▶│                        │
   │                        │── approve(txId) ──────▶│
   │── execute(txId) ───────────────────────────────▶│
   │                        │                 _executeTransfer()
   │                        │                 to.call{value}()
```

### Flow 2 — Investment Strategy

```
Backend                Frontend              Admin A            Admin B          Contract            Protocol
   │                      │                    │                   │                │                   │
   │◀── GET /api/strategies/opportunities ────│                   │                │                   │
   │ ① Read Chainlink prices (all tokens)     │                   │                │                   │
   │ ② Scan all pairs via Uniswap V3 slot0    │                   │                │                   │
   │ ③ Query Compound/Aave APY                │                   │                │                   │
   │ ④ Rank pairs by |spread|, pick best      │                   │                │                   │
   │ ⑤ Encode calldata (supply/swap)          │                   │                │                   │
   │─── StrategyRecommendation[] ────────────▶│                   │                │                   │
   │    {protocol, calldata, apy, risk}       │                   │                │                   │
   │                                          │                   │                │                   │
   │                              "Create Proposal" click         │                │                   │
   │                                          │── proposeStrategy(protocol,        │                   │
   │                                          │     calldata, LENDING/ARBITRAGE) ─▶│                   │
   │                                          │                   │   emit StrategyProposed            │
   │                                          │                   │── approve(txId) ──────────────────▶│
   │                                          │                   │                │ emit Approved      │
   │                                          │                   │                │── execute(txId) ──▶│
   │                                          │                   │                │  _executeStrategy()│
   │                                          │                   │                │  ERC20.approve()   │
   │                                          │                   │                │  protocol.call() ─▶│
   │                                          │                   │                │   emit StrategyExecuted
```

### Flow 3 — Multi-Pair Arbitrage Scan

```
GET /api/strategies/scan
        │
        ▼
PriceService.get_all_token_prices()
  └─ Chainlink: WETH=$3200, WBTC=$65000, USDC=$1.00, LINK=$18.5, UNI=$12.1

For each pair in ARBITRAGE_PAIRS:
  ┌──────────────────────────────────────────────────────────┐
  │ WETH/USDC  chainlink=3200.00  dex=3213.44  spread=+0.42% │ ← best
  │ WETH/WBTC  chainlink=0.04923  dex=0.04930  spread=+0.14% │
  │ LINK/WETH  chainlink=0.00578  dex=0.00575  spread=-0.52% │ ← best (abs)
  │ WBTC/USDC  chainlink=65000.0  dex=64932.0  spread=-0.10% │
  │ UNI/WETH   chainlink=0.00378  dex=0.00379  spread=+0.03% │
  └──────────────────────────────────────────────────────────┘
        │
        ▼  sort by abs(spread) descending
        │
  Only pairs with abs(spread) ≥ ARBITRAGE_MIN_SPREAD_PCT (0.3%)
  → converted to StrategyRecommendation with Uniswap swap calldata
```

---

## Project Structure

```
blockchain-final/
├── src/                                    # Smart contracts
│   ├── MultisigWalletWithStrategies.sol    # Main contract
│   └── interfaces/
│       ├── IChainlinkAggregator.sol        # Chainlink AggregatorV3Interface
│       └── IERC20.sol                      # ERC20 approve / balanceOf
├── test/
│   └── MultisigWalletWithStrategies.t.sol  # 26 tests
├── script/
│   └── DeployMultisigWithStrategies.s.sol  # Forge deploy script
├── backend/                                # Python strategy engine
│   ├── main.py                             # FastAPI app entry
│   ├── config.py                           # Token registry + pair list
│   ├── requirements.txt
│   ├── .env.example
│   ├── models/
│   │   └── strategy.py                     # Pydantic data models
│   ├── services/
│   │   ├── price_service.py                # Chainlink feeds + Uniswap V3 slot0
│   │   ├── lending_service.py              # Compound & Aave APY queries
│   │   ├── dex_service.py                  # QuoterV2 estimate + swap calldata
│   │   └── strategy_engine.py             # Multi-pair scanner + calldata
│   └── routers/
│       ├── prices.py                       # GET /api/prices
│       ├── strategies.py                   # GET /api/strategies/*
│       └── calldata.py                     # POST /api/calldata/encode
└── web_app/                                # Frontend
    ├── index.html
    ├── styles.css
    └── script.js
```

---

## Smart Contract: `MultisigWalletWithStrategies`

### Key Design Decisions

| Aspect | MultisigWalletWithAave (old) | MultisigWalletWithStrategies (new) |
|--------|------------------------------|-------------------------------------|
| Proposal types | TRANSFER, AAVE_DEPOSIT, AAVE_WITHDRAW | TRANSFER, STRATEGY |
| Strategy types | — | LENDING, ARBITRAGE |
| Protocol coupling | Hardcoded Aave addresses | Protocol whitelist (`approvedProtocols`) |
| Price oracle | None | Chainlink ETH/USD, BTC/USD (on-chain) |
| Calldata source | Contract generates | Backend generates, contract executes |
| ERC20 approval | Contract-internal | Contract approves before calling protocol |

### Proposal Struct

```solidity
struct Proposal {
    address to;           // target protocol (must be whitelisted)
    uint256 value;        // ETH to forward (0 for ERC20 strategies)
    bytes data;           // ABI-encoded calldata from backend
    string description;
    bool executed;
    uint256 approvalCount;
    ProposalType proposalType;  // TRANSFER | STRATEGY
    StrategyType strategyType;  // NONE | LENDING | ARBITRAGE
    address tokenIn;            // ERC20 to approve (address(0) = ETH)
    uint256 amountIn;           // amount to approve
}
```

### Key Functions

| Function | Access | Description |
|----------|--------|-------------|
| `propose(to, value, data, desc)` | Admin | Create ETH transfer proposal |
| `proposeStrategy(protocol, ethValue, calldata, desc, type, tokenIn, amountIn)` | Admin | Create strategy proposal |
| `approve(txId)` | Admin | Add approval vote |
| `execute(txId)` | Admin | Execute when threshold reached |
| `approveProtocol(addr, name)` | Admin | Add protocol to whitelist |
| `revokeProtocol(addr)` | Admin | Remove protocol from whitelist |
| `getEthUsdPrice()` | Public | Read Chainlink ETH/USD |
| `getBtcUsdPrice()` | Public | Read Chainlink BTC/USD |
| `isPriceFresh(updatedAt)` | Public | Check if price is within stale threshold |

### Strategy Execution (internal)

```solidity
function _executeStrategy(uint256 txId, Proposal storage p) internal {
    require(approvedProtocols[p.to], "Protocol not approved");

    // Approve ERC20 allowance for the protocol (e.g. USDC for Compound supply)
    if (p.tokenIn != address(0) && p.amountIn > 0) {
        IERC20(p.tokenIn).approve(p.to, p.amountIn);
    }

    // Execute the backend-generated calldata
    (bool success, bytes memory returnData) = p.to.call{value: p.value}(p.data);

    // Bubble up revert reason on failure
    if (!success) { assembly { revert(add(32, returnData), mload(returnData)) } }

    emit StrategyExecuted(txId, p.strategyType, p.to);
}
```

---

## Backend Strategy Engine

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/prices` | ETH/USD, BTC/USD from Chainlink; all token prices; ETH/BTC ratio |
| `GET` | `/api/strategies/opportunities` | All lending + arbitrage recommendations (above threshold) |
| `GET` | `/api/strategies/lending` | Lending recommendations only |
| `GET` | `/api/strategies/arbitrage` | Arbitrage recommendations only (above spread threshold) |
| `GET` | `/api/strategies/scan` | Raw scan of **all** configured pairs — sorted by spread, includes below-threshold |
| `POST` | `/api/calldata/encode` | Encode calldata for a given strategy |

### Token Registry

The backend uses a configurable token registry (`config.TOKENS`) instead of hardcoded addresses. Default tokens (mainnet):

| Symbol | Address | Chainlink Feed | Default Trade Amount |
|--------|---------|---------------|---------------------|
| WETH | `0xC02a...Cc2` | ETH/USD `0x5f4e...419` | 0.1 WETH |
| WBTC | `0x2260...599` | BTC/USD `0xF403...88c` | 0.001 WBTC |
| USDC | `0xA0b8...B48` | USDC/USD `0x8fFf...6` | 1000 USDC |
| LINK | `0x5149...CA` | LINK/USD `0x2c1d...27c` | 10 LINK |
| UNI | `0x1f98...984` | UNI/USD `0x5533...20e` | 10 UNI |

Add new tokens without changing code:
```bash
EXTRA_TOKENS_JSON='{"AAVE":{"address":"0x7Fc...","decimals":18,"chainlink_usd":"0x547...","default_amount":"1000000000000000000"}}'
```

### Arbitrage Pair List

The backend scans all pairs in `config.ARBITRAGE_PAIRS` and ranks by absolute spread:

| Pair | Pool Address | Fee |
|------|-------------|-----|
| WETH / USDC | `0x88e6...640` | 0.05% |
| WETH / WBTC | `0xCBCd...eD` | 0.30% |
| WBTC / USDC | `0x99ac...35` | 0.30% |
| LINK / WETH | `0xa6Cc...e8` | 0.30% |
| UNI / WETH | `0x1d42...01` | 0.30% |

Override all pairs without changing code:
```bash
ARBITRAGE_PAIRS_JSON='[{"token0":"WETH","token1":"USDC","pool_address":"0x88e6...","fee":500}]'
```

### Strategy Types

#### Lending Strategy

1. Query **Compound V3** supply rate: `getSupplyRate(getUtilization())` → convert to APY
2. Query **Aave V3** supply rate: `getReserveData(asset).currentLiquidityRate` (RAY → APY)
3. Compare → recommend protocol with higher yield (if APY > `LENDING_MIN_APY_PCT`)
4. Encode calldata: `Comet.supply(asset, amount)` or `AavePool.supply(asset, amount, wallet, 0)`

#### Arbitrage Strategy (Multi-Pair)

1. Read **Chainlink** USD prices for all tokens in one pass
2. For each pair: `chainlink_ratio = price_token0 / price_token1`
3. Read **Uniswap V3** pool price — handles canonical token ordering automatically
4. Compute `spread_pct = (dex_ratio - chainlink_ratio) / chainlink_ratio × 100`
5. Sort all pairs by `abs(spread_pct)` descending
6. For pairs above `ARBITRAGE_MIN_SPREAD_PCT` (default 0.3%), encode `exactInputSingle` calldata via QuoterV2 with 0.5% slippage protection

### Data Models

#### `PriceSnapshot`

```python
class PriceSnapshot(BaseModel):
    eth_usd: float
    btc_usd: float
    eth_btc_ratio: float
    updated_at: int              # unix timestamp of Chainlink answer
    is_fresh: bool
    token_prices: dict[str, float]  # {WETH: 3200.0, WBTC: 65000.0, ...}
```

#### `PairScanResult`

```python
class PairScanResult(BaseModel):
    token0_symbol: str
    token1_symbol: str
    pool_address: str
    fee_tier: int
    chainlink_ratio: float       # token0_usd / token1_usd (expected price)
    dex_ratio: float             # actual DEX price (token1 per token0)
    spread_pct: float            # (dex - chainlink) / chainlink * 100
    spread_direction: str        # e.g. "Sell WETH→USDC (DEX overprices WETH)"
    above_threshold: bool
    error: Optional[str]
```

#### `StrategyRecommendation`

```python
class StrategyRecommendation(BaseModel):
    id: str                        # unique ID
    strategy_type: StrategyType    # "lending" | "arbitrage"
    protocol_name: str             # e.g. "Compound V3"
    protocol_address: str          # checksum address
    description: str               # human-readable
    expected_return_pct: float     # annualised % APY or spread
    risk_score: int                # 1 (low) – 10 (high)
    token_in: str                  # ERC20 address or "ETH"
    token_in_symbol: str
    amount_suggestion_wei: str     # suggested input amount
    calldata: str                  # 0x hex – ready to submit to proposeStrategy()
    eth_value: str                 # ETH to forward (usually "0")
    price_snapshot: PriceSnapshot  # {eth_usd, btc_usd, token_prices, ...}
    expires_at: int                # unix timestamp (lending: 5 min, arbitrage: 1 min)
```

---

## Prerequisites

1. **Install Foundry**
```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

2. **Install Python 3.10+**
```bash
python --version
```

3. **Get an RPC URL** (Infura or Alchemy) for Mainnet or Sepolia

---

## Quick Start

### 1. Build & Test Contracts

```bash
forge build
forge test                                        # all test suites
forge test --match-contract MultisigWalletWithStrategiesTest -v  # new tests only
```

### 2. Start Local Blockchain (Mainnet Fork — for real Chainlink data)

```bash
export MAINNET_RPC_URL=https://mainnet.infura.io/v3/YOUR_KEY
anvil --fork-url $MAINNET_RPC_URL
```

### 3. Deploy Contract

```bash
export PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

forge script script/DeployMultisigWithStrategies.s.sol:DeployMultisigWithStrategies \
    --rpc-url http://127.0.0.1:8545 \
    --broadcast
```

The script prints the deployed address. Save it.

### 4. Whitelist Protocols

```bash
export CONTRACT=0xYOUR_DEPLOYED_CONTRACT

# Uniswap V3 Router
cast send $CONTRACT "approveProtocol(address,string)" \
    0xE592427A0AEce92De3Edee1F18E0157C05861564 "Uniswap V3 Router" \
    --private-key $PRIVATE_KEY --rpc-url http://127.0.0.1:8545

# Compound V3 USDC
cast send $CONTRACT "approveProtocol(address,string)" \
    0xc3d688B66703497DAA19211EEdff47f25384cdc3 "Compound V3 USDC" \
    --private-key $PRIVATE_KEY --rpc-url http://127.0.0.1:8545

# Aave V3 Pool
cast send $CONTRACT "approveProtocol(address,string)" \
    0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2 "Aave V3 Pool" \
    --private-key $PRIVATE_KEY --rpc-url http://127.0.0.1:8545
```

### 5. Configure and Start the Backend

```bash
cd backend
cp .env.example .env
```

Edit `.env`:
```
RPC_URL=http://127.0.0.1:8545
CONTRACT_ADDRESS=0xYOUR_DEPLOYED_CONTRACT
```

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Verify: open `http://localhost:8000/docs` to see the Swagger UI.

Test multi-pair scan:
```bash
curl http://localhost:8000/api/strategies/scan | python -m json.tool
```

### 6. Update and Run Frontend

In [web_app/script.js](web_app/script.js), set:
```javascript
const CONTRACT_ADDRESS = "0xYOUR_DEPLOYED_CONTRACT";
const BACKEND_URL = "http://localhost:8000";
```

```bash
cd web_app
python -m http.server 8080
```

Open `http://localhost:8080`. Connect MetaMask to **Anvil local network**:
- Network name: `Anvil Local`
- RPC URL: `http://127.0.0.1:8545`
- Chain ID: `31337`

---

## Demo Scenarios

### Scenario A — Transfer ETH

1. **Alice** connects MetaMask, clicks **Create Proposal → Transfer ETH**
2. Sets recipient = Bob's address, amount = 0.5 ETH, description = "Pay Bob"
3. Contract emits `ProposalCreated`
4. **Bob** connects, goes to **Proposals**, clicks **Approve**
5. **Alice** clicks **Execute** (her execute counts as 2nd approval → threshold reached)
6. 0.5 ETH transferred, `Executed` event emitted

### Scenario B — Lending Strategy

1. **Backend** compares Compound V3 APY vs Aave V3 APY for USDC
2. Compound offers 5.2% → Backend returns `StrategyRecommendation` with:
   - `protocol_address = Compound V3 USDC`
   - `calldata = supply(USDC, 1000e6)` (ABI-encoded)
   - `expected_return_pct = 5.2`
3. **Frontend** shows strategy card with "5.2% APY / Risk: 2/10"
4. **Alice** clicks **Create Proposal** → form auto-fills protocol + calldata
5. **Bob** approves, **Alice** executes
6. Contract calls `USDC.approve(Compound, 1000e6)` then `Compound.supply(USDC, 1000e6)`
7. Wallet receives cUSDC (receipt token)

### Scenario C — Multi-Pair Arbitrage

1. **Backend** scans all 5 pairs simultaneously:
   - WETH/USDC: spread = **+0.42%** ← best
   - LINK/WETH: spread = -0.31%
   - WETH/WBTC: spread = +0.08% (below threshold)
   - …
2. Pairs above 0.3% threshold → generate proposals sorted best-first
3. For WETH/USDC: DEX price ($3213) > Chainlink ($3200) → sell WETH, buy USDC:
   - `token_in = WETH`, `token_out = USDC`, `fee = 500`
   - `calldata = exactInputSingle(WETH→USDC, ...)`
4. Admin creates proposal → approve → execute
5. Wallet swaps 0.1 WETH for more USDC than the Chainlink ratio implies → profit

### Scenario D — Raw Pair Scan (monitoring)

```bash
# Check which pairs are closest to arbitrage threshold right now
curl http://localhost:8000/api/strategies/scan
# Returns all 5 pairs sorted by abs(spread), even those below 0.3%
# Useful for monitoring: shows spread trending toward threshold
```

---

## Deploy to Sepolia Testnet

```bash
export PRIVATE_KEY=your_private_key
export SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_KEY

forge script script/DeployMultisigWithStrategies.s.sol:DeployMultisigWithStrategies \
    --rpc-url $SEPOLIA_RPC_URL \
    --broadcast \
    --verify
```

Update `.env` in backend:
```
RPC_URL=https://sepolia.infura.io/v3/YOUR_KEY
CHAINLINK_ETH_USD=0x694AA1769357215DE4FAC081bf1f309aDC325306
CHAINLINK_BTC_USD=0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43
```

> **Note:** LINK/USD, UNI/USD Chainlink feeds and the LINK/WETH, UNI/WETH Uniswap pools are not available on Sepolia. Set `ARBITRAGE_PAIRS_JSON` to only include pairs available on the testnet.

---

## Chainlink Price Feed Addresses

| Network | Pair | Address |
|---------|------|---------|
| Mainnet | ETH/USD | `0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419` |
| Mainnet | BTC/USD | `0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c` |
| Mainnet | USDC/USD | `0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6` |
| Mainnet | LINK/USD | `0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c` |
| Mainnet | UNI/USD | `0x553303d460EE0afB37EdFf9bE42922D8FF63220e` |
| Sepolia | ETH/USD | `0x694AA1769357215DE4FAC081bf1f309aDC325306` |
| Sepolia | BTC/USD | `0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43` |

## Protocol Addresses

| Protocol | Network | Address |
|----------|---------|---------||
| Uniswap V3 Router | Mainnet + Sepolia | `0xE592427A0AEce92De3Edee1F18E0157C05861564` |
| Uniswap QuoterV2 | Mainnet + Sepolia | `0x61fFE014bA17989E743c5F6cB21bF9697530B21e` |
| Compound V3 USDC (Comet) | Mainnet | `0xc3d688B66703497DAA19211EEdff47f25384cdc3` |
| Aave V3 Pool | Mainnet | `0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2` |

## Uniswap V3 Pool Addresses (Mainnet)

| Pair | Fee | Pool Address |
|------|-----|-------------|
| WETH / USDC | 0.05% | `0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640` |
| WETH / WBTC | 0.30% | `0xCBCdF9626bC03E24f779434178A73a0B4bad62eD` |
| WBTC / USDC | 0.30% | `0x99ac8cA7087fA4A2A1FB6357269965A2014ABc35` |
| LINK / WETH | 0.30% | `0xa6Cc3C2531FdaA6Ae1A3CA84c2855806728693e8` |
| UNI / WETH | 0.30% | `0x1d42064Fc4Beb5F8aAF85F4617AE8b3b5B8Bd801` |

---

## Security Considerations

- **Protocol whitelist** — Only pre-approved protocols can receive contract calls; any admin can add/revoke
- **Multisig threshold** — All strategy executions require N-of-M approvals, same as transfers
- **Calldata validation** — The contract trusts calldata generated by the backend; admins should verify the description before approving
- **Price freshness** — `isPriceFresh(updatedAt)` checks that Chainlink data is within `priceStaleThreshold` (default 1 hour); `PriceSnapshot.is_fresh` surfaces this to the frontend
- **Slippage** — Arbitrage swaps use a 0.5% slippage tolerance via `amountOutMinimum` (estimated by QuoterV2)
- **Short expiry** — Arbitrage recommendations expire in 60 seconds; lending in 5 minutes — stale recommendations should not be submitted
- **Canonical pool ordering** — `get_pool_price_ratio()` reads `pool.token0()` on-chain to handle cases where pool address ordering differs from pair config; prevents inverted price calculations
- **Testnet first** — Always test on Sepolia before deploying to mainnet

---

## Testing

```bash
# All tests
forge test

# New strategy contract tests (26 tests)
forge test --match-contract MultisigWalletWithStrategiesTest -v

# With mainnet fork (tests Chainlink + Uniswap live data)
forge test --fork-url $MAINNET_RPC_URL
```

Test coverage of `MultisigWalletWithStrategies`:
- Constructor validation
- Protocol whitelist (approve / revoke / duplicate / non-admin)
- Transfer proposals (propose / approve / execute)
- Strategy proposals (whitelist required, correct enum stored)
- Strategy execution (success, protocol-reverts bubbles up, revoked-before-execute)
- Chainlink price reading (ETH/USD, BTC/USD, stale check)
- Access control (only admin, cannot approve twice, cannot execute twice, insufficient approvals)

---

## License

MIT
