# Group Multisig Asset Manager

A decentralized application (DApp) for group fund management with multi-signature security and Aave yield farming integration.

## Features

- **Multi-Signature Wallet**: Secure fund management requiring multiple admin approvals
- **Proposal System**: Create, approve, and execute fund transfer proposals
- **Aave Integration**: Earn yield on idle funds through Aave Protocol
- **Web Interface**: User-friendly dashboard for managing the wallet

## Project Structure

```
blockchain-final/
├── src/                          # Smart contracts
│   ├── MultisigWallet.sol        # Basic multisig wallet
│   ├── MultisigWalletWithAave.sol # Multisig with Aave integration
│   ├── AaveSupplier.sol          # Standalone Aave integration
│   ├── AaveAddresses.sol         # Aave contract addresses
│   └── interfaces/               # Contract interfaces
├── test/                         # Test files
│   └── MultisigWallet.t.sol      # Multisig tests
├── script/                       # Deployment scripts
│   ├── DeployMultisig.s.sol      # Deploy basic wallet
│   └── DeployMultisigWithAave.s.sol # Deploy with Aave
├── web_app/                      # Frontend application
│   ├── index.html                # Main HTML
│   ├── styles.css                # CSS styles
│   └── script.js                 # JavaScript logic
└── foundry.toml                  # Foundry configuration
```

## Prerequisites

1. **Install Foundry**
```bash
# Download and install Foundry
curl -L https://foundry.paradigm.xyz | bash

# Run foundryup to install forge, cast, anvil
foundryup
```

2. **Install Dependencies**
```bash
# Install forge-std for testing
forge install foundry-rs/forge-std --no-commit

# Install OpenZeppelin contracts (optional)
forge install OpenZeppelin/openzeppelin-contracts --no-commit
```

## Quick Start

### 1. Build Contracts

```bash
forge build
```

### 2. Run Tests

```bash
# Run all tests
forge test

# Run with verbosity
forge test -vvv

# Run specific test
forge test --match-contract MultisigWalletTest
```

### 3. Start Local Blockchain

```bash
# Start Anvil local node
anvil
```

### 4. Deploy to Local Network

Open a new terminal:

```bash
# Set private key (use one from Anvil output)
export PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# Deploy basic MultisigWallet
forge script script/DeployMultisig.s.sol:DeployMultisig \
    --rpc-url http://127.0.0.1:8545 \
    --broadcast

# Or deploy MultisigWalletWithAave
forge script script/DeployMultisigWithAave.s.sol:DeployMultisigWithAave \
    --rpc-url http://127.0.0.1:8545 \
    --broadcast
```

### 5. Update Frontend

1. Copy the deployed contract address from the deployment output
2. Open `web_app/script.js`
3. Update `CONTRACT_ADDRESS` with your deployed address
4. Update `CONTRACT_ABI` if needed (copy from `out/MultisigWallet.sol/MultisigWallet.json`)

### 6. Run Frontend

Open `web_app/index.html` in your browser, or use a local server:

```bash
# Using Python
cd web_app
python -m http.server 8080

# Or using Node.js
npx serve web_app
```

## Deploy to Sepolia Testnet

1. Get Sepolia ETH from a faucet
2. Set up environment variables:

```bash
export PRIVATE_KEY=your_private_key
export SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/your_key
```

3. Deploy:

```bash
forge script script/DeployMultisigWithAave.s.sol:DeployMultisigWithAave \
    --rpc-url $SEPOLIA_RPC_URL \
    --broadcast \
    --verify
```

## Contract Functions

### MultisigWallet

| Function | Description |
|----------|-------------|
| `propose(to, value, data, description)` | Create a new proposal |
| `approve(txId)` | Approve a pending proposal |
| `execute(txId)` | Execute an approved proposal |
| `getProposal(txId)` | Get proposal details |
| `canExecute(txId)` | Check if proposal can be executed |
| `getBalance()` | Get wallet ETH balance |

### MultisigWalletWithAave (additional)

| Function | Description |
|----------|-------------|
| `proposeAaveDeposit(asset, amount, description)` | Propose depositing to Aave |
| `proposeAaveWithdraw(asset, amount, description)` | Propose withdrawing from Aave |
| `getAaveBalance(aToken)` | Get aToken balance |
| `getAaveAccountData()` | Get Aave account info |

## Demo Scenario

1. **Setup**: Deploy contract with 3 admins (Alice, Bob, Carol), threshold = 2

2. **Alice proposes**: Send 0.1 ETH to a vendor
   ```javascript
   await contract.propose(vendorAddress, ethers.utils.parseEther("0.1"), "0x", "Pay vendor");
   ```

3. **Bob approves**:
   ```javascript
   await contract.approve(0);
   ```

4. **Alice executes** (her execution counts as approval, now 2/2):
   ```javascript
   await contract.execute(0);
   ```

5. **Verify** the transaction on Etherscan

## Testing with Aave (Mainnet Fork)

To test Aave integration locally:

```bash
# Set mainnet RPC URL
export MAINNET_RPC_URL=https://mainnet.infura.io/v3/your_key

# Run tests with fork
forge test --fork-url $MAINNET_RPC_URL --match-contract AaveTest
```

## Security Considerations

- Always verify contract addresses before deployment
- Use hardware wallets for admin accounts in production
- Test thoroughly on testnet before mainnet deployment
- Consider using a time-lock for large transfers

## Gas Optimization

- The contract uses efficient storage patterns
- Mappings are preferred over arrays for lookups
- Events are used for historical data instead of storage

## License

MIT
