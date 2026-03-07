// ============================================================
// Group Multisig Wallet with Investment Strategies - Frontend
// ============================================================

// ---- Contract Configuration (update after forge deploy) ----
const CONTRACT_ADDRESS = "0x195FA537B17734Bb4fDEE405146dAb5F9Dca72be";
const BACKEND_URL = "http://localhost:8000";

// ---- Contract ABI for MultisigWalletWithStrategies ----
const CONTRACT_ABI = [
    // Events
    "event Deposit(address indexed sender, uint256 amount, uint256 balance)",
    "event ProposalCreated(uint256 indexed txId, address indexed proposer, address indexed to, uint256 value, string description)",
    "event Approved(address indexed admin, uint256 indexed txId)",
    "event Executed(uint256 indexed txId)",
    "event StrategyProposed(uint256 indexed txId, uint8 strategyType, address indexed protocol, address tokenIn, uint256 amountIn)",
    "event StrategyExecuted(uint256 indexed txId, uint8 strategyType, address indexed protocol)",
    "event ProtocolApproved(address indexed protocol, string name)",
    "event ProtocolRevoked(address indexed protocol)",

    // Read – admin / wallet info
    "function admins(uint256) view returns (address)",
    "function isAdmin(address) view returns (bool)",
    "function threshold() view returns (uint256)",
    "function getAdminCount() view returns (uint256)",
    "function getAdmins() view returns (address[])",
    "function getBalance() view returns (uint256)",
    "function getTokenBalance(address) view returns (uint256)",

    // Read – proposals
    "function getProposalCount() view returns (uint256)",
    "function getProposal(uint256) view returns (address to, uint256 value, bytes data, string description, bool executed, uint256 approvalCount, uint8 proposalType, uint8 strategyType, address tokenIn, uint256 amountIn)",
    "function canExecute(uint256) view returns (bool)",
    "function hasApproved(uint256, address) view returns (bool)",

    // Read – protocol whitelist
    "function approvedProtocols(address) view returns (bool)",
    "function getApprovedProtocols() view returns (address[])",

    // Read – Chainlink prices
    "function getEthUsdPrice() view returns (int256 price, uint256 updatedAt)",
    "function getBtcUsdPrice() view returns (int256 price, uint256 updatedAt)",
    "function isPriceFresh(uint256) view returns (bool)",
    "function priceStaleThreshold() view returns (uint256)",

    // Write – standard transfer
    "function propose(address _to, uint256 _value, bytes _data, string _description) returns (uint256)",

    // Write – strategy proposal
    "function proposeStrategy(address _protocol, uint256 _ethValue, bytes _calldata, string _description, uint8 _strategyType, address _tokenIn, uint256 _amountIn) returns (uint256)",

    // Write – approval / execution
    "function approve(uint256 _txId)",
    "function execute(uint256 _txId)",

    // Write – protocol whitelist
    "function approveProtocol(address _protocol, string _name)",
    "function revokeProtocol(address _protocol)",
];

// StrategyType enum values (must match Solidity enum order)
const StrategyType = { NONE: 0, LENDING: 1, ARBITRAGE: 2 };

// Tracked Portfolio Tokens (Aave aTokens, Compound cTokens)
const PORTFOLIO_ASSETS = [
    {
        symbol: "aWETH", name: "Aave V3 WETH", address: "0x4d5f47fa6a74757f35c14fd3a6ef8e3c9bc514e8", decimals: 18,
        withdrawCall: {
            protocol: "0xd01607c3C5eCABa394D8be377a08590149325722", // WETH_GATEWAY
            tokenIn: "0x4d5f47fa6a74757f35c14fd3a6ef8e3c9bc514e8",  // Approve aWETH to Gateway
            abi: ["function withdrawETH(address pool, uint256 amount, address to)"]
        }
    },
    {
        symbol: "aUSDC", name: "Aave V3 USDC", address: "0x98c23e9d8f34fea023834e462b2dcee2bed9ba25", decimals: 6,
        withdrawCall: {
            protocol: "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2", // AAVE_POOL
            tokenIn: "0x0000000000000000000000000000000000000000",
            abi: ["function withdraw(address asset, uint256 amount, address to) returns (uint256)"]
        }
    },
    {
        symbol: "cUSDCv3", name: "Compound V3 USDC", address: "0xc3d688b66703497daa19211eedff47f25384cdc3", decimals: 6,
        withdrawCall: {
            protocol: "0xc3d688B66703497DAA19211EEdff47f25384cdc3", // COMET Mainnet
            tokenIn: "0x0000000000000000000000000000000000000000",
            abi: ["function withdraw(address asset, uint256 amount)"]
        }
    },
    {
        symbol: "aWBTC", name: "Aave V3 WBTC", address: "0x5ee5bf7ae06d1be5997a1a72006fe6c607ec6de8", decimals: 8,
        withdrawCall: {
            protocol: "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2", // AAVE_POOL
            tokenIn: "0x0000000000000000000000000000000000000000",
            abi: ["function withdraw(address asset, uint256 amount, address to) returns (uint256)"]
        }
    }
];

// Global state
let provider, signer, contract;
let currentAccount = null;
let isAdmin = false;

// Price refresh interval (30 s)
let priceInterval = null;

// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
});

async function initializeApp() {
    if (typeof window.ethereum !== 'undefined') {
        const accounts = await window.ethereum.request({ method: 'eth_accounts' });
        if (accounts.length > 0) await connectWallet();
        window.ethereum.on('accountsChanged', handleAccountsChanged);
        window.ethereum.on('chainChanged', () => window.location.reload());
    } else {
        showToast('Please install MetaMask to use this DApp', 'error');
    }
    // Start polling backend prices even before wallet connects
    startPriceTicker();
}

function setupEventListeners() {
    document.getElementById('connectBtn').addEventListener('click', connectWallet);

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
            if (btn.dataset.tab === 'strategies') loadStrategies();
            if (btn.dataset.tab === 'portfolio') loadPortfolio();
        });
    });

    document.getElementById('createProposalBtn').addEventListener('click', createProposal);
    document.getElementById('proposalType').addEventListener('change', handleProposalTypeChange);
    document.getElementById('refreshStrategiesBtn').addEventListener('click', loadStrategies);

    // Live update helper text when typing in "Amount In (wei)" field
    const amtInput = document.getElementById('strategyAmountIn');
    if (amtInput) {
        amtInput.addEventListener('input', (e) => {
            const val = e.target.value.trim();
            let helper = document.getElementById('strategyAmountInHelper');
            if (!helper) {
                helper = document.createElement('small');
                helper.id = 'strategyAmountInHelper';
                helper.style.display = 'block';
                helper.style.color = '#10b981';
                helper.style.marginTop = '4px';
                amtInput.parentNode.appendChild(helper);
            }

            if (!val || isNaN(val)) {
                helper.innerText = '';
                return;
            }

            try {
                // Try to format dynamically, default to 18 decimals if cannot find reference
                const tokenInAddress = document.getElementById('strategyTokenIn').value;
                const isUSDC = tokenInAddress && tokenInAddress.toLowerCase() === "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48";
                const decimals = isUSDC ? 6 : 18;
                const readableAmount = ethers.utils.formatUnits(val, decimals);
                helper.innerText = `≈ ${readableAmount} tokens`;

                // If this is a WETH Gateway native ETH deposit, sync ethValue and rewrite Calldata
                const protocolInput = document.getElementById('strategyProtocol').value;
                if (protocolInput && protocolInput.toLowerCase() === "0xd01607c3c5ecaba394d8be377a08590149325722") { // WETH_GATEWAY
                    const ethValInput = document.getElementById('strategyEthValue');
                    if (ethValInput) {
                        ethValInput.value = val;
                        // update ethHelper
                        const ethHelper = document.getElementById('strategyEthHelper');
                        if (ethHelper) ethHelper.innerText = `+ Sending ${readableAmount} natively attached ETH`;
                    }

                    // Rewrite calldata: depositETH(address pool, address onBehalfOf, uint16 referralCode)
                    // The Aave pool address is: 0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2
                    const iface = new ethers.utils.Interface([
                        "function depositETH(address pool, address onBehalfOf, uint16 referralCode) payable"
                    ]);
                    const newCalldata = iface.encodeFunctionData("depositETH", [
                        "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
                        contract.address,
                        0
                    ]);
                    document.getElementById('strategyCalldata').value = newCalldata;
                }
            } catch (err) {
                helper.innerText = 'Invalid amount';
            }
        });
    }
}

// ============================================================
// WALLET CONNECTION
// ============================================================

async function connectWallet() {
    try {
        if (typeof window.ethereum === 'undefined') {
            showToast('MetaMask not found. Please install MetaMask extension.', 'error');
            return;
        }
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        currentAccount = accounts[0].toLowerCase();

        provider = new ethers.providers.Web3Provider(window.ethereum);
        signer = provider.getSigner();
        contract = new ethers.Contract(CONTRACT_ADDRESS, CONTRACT_ABI, signer);

        await updateAccountUI();
        await loadDashboardData();
        await loadProposals();
        await loadPortfolio();
        setupContractEvents();

        showToast('Wallet connected successfully!', 'success');
    } catch (error) {
        console.error('Error connecting wallet:', error);
        showToast('Failed to connect wallet: ' + shortError(error.message), 'error');
    }
}

async function handleAccountsChanged(accounts) {
    if (accounts.length === 0) {
        currentAccount = null;
        document.getElementById('connectBtn').classList.remove('hidden');
        document.getElementById('accountInfo').classList.add('hidden');
    } else {
        currentAccount = accounts[0].toLowerCase();
        await updateAccountUI();
        await loadDashboardData();
        await loadProposals();
    }
}

async function updateAccountUI() {
    document.getElementById('connectBtn').classList.add('hidden');
    document.getElementById('accountInfo').classList.remove('hidden');
    document.getElementById('accountAddress').textContent =
        `${currentAccount.slice(0, 6)}...${currentAccount.slice(-4)}`;
    console.log(`${currentAccount.slice(0, 6)}...${currentAccount.slice(-4)}`);
    try {
        isAdmin = await contract.isAdmin(currentAccount);
        const role = document.getElementById('accountRole');
        role.textContent = isAdmin ? 'Admin' : 'Guest';
        role.className = `badge ${isAdmin ? 'admin' : 'guest'}`;
    } catch (e) {
        console.error(e);
    }
}

// ============================================================
// PRICE TICKER (backend)
// ============================================================

function startPriceTicker() {
    fetchAndDisplayPrices();
    priceInterval = setInterval(fetchAndDisplayPrices, 30_000);
}

async function fetchAndDisplayPrices() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/prices`);
        if (!res.ok) return;
        const data = await res.json();

        const fmt = n => '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 });

        document.getElementById('tickerEthUsd').textContent = fmt(data.eth_usd);
        document.getElementById('tickerBtcUsd').textContent = fmt(data.btc_usd);

        const fresh = document.getElementById('tickerFreshness');
        if (!data.is_fresh) {
            fresh.textContent = '⚠ stale price';
            fresh.className = 'price-item price-stale';
            fresh.style.display = '';
        } else {
            fresh.style.display = 'none';
        }

        // Dashboard card
        document.getElementById('dashEthPrice').textContent = fmt(data.eth_usd);
        document.getElementById('dashEthBtcRatio').textContent =
            `ETH/BTC ${Number(data.eth_btc_ratio).toFixed(5)}`;
    } catch (e) {
        // Backend may not be running yet – fail silently
    }
}

// ============================================================
// DASHBOARD DATA
// ============================================================

async function loadDashboardData() {
    if (!contract) return;
    try {
        const balance = await contract.getBalance();
        document.getElementById('walletBalance').textContent =
            `${ethers.utils.formatEther(balance)} ETH`;

        const threshold = await contract.threshold();
        const adminCount = await contract.getAdminCount();
        document.getElementById('thresholdInfo').textContent = `${threshold}/${adminCount}`;

        const admins = await contract.getAdmins();
        displayAdmins(admins);

        const proposalCount = await contract.getProposalCount();
        let pending = 0;
        for (let i = 0; i < proposalCount; i++) {
            const p = await contract.getProposal(i);
            if (!p.executed) pending++;
        }
        document.getElementById('pendingCount').textContent = pending;

    } catch (e) {
        console.error('Error loading dashboard data:', e);
        showToast('Error loading dashboard data', 'error');
    }
}

function displayAdmins(admins) {
    const list = document.getElementById('adminsList');
    list.innerHTML = '';
    admins.forEach(admin => {
        const badge = document.createElement('div');
        badge.className = `admin-badge ${admin.toLowerCase() === currentAccount ? 'current' : ''}`;
        badge.textContent = `${admin.slice(0, 6)}...${admin.slice(-4)}`;
        list.appendChild(badge);
    });
}

// ============================================================
// PORTFOLIO
// ============================================================

async function loadPortfolio() {
    if (!contract) return;
    try {
        const container = document.getElementById('portfolioList');
        // keep old content briefly until we get new data
        let html = '';
        let hasActivePositions = false;

        for (const asset of PORTFOLIO_ASSETS) {
            try {
                const balanceWei = await contract.getTokenBalance(asset.address);
                if (balanceWei.gt(0)) {
                    hasActivePositions = true;
                    const formattedBalance = ethers.utils.formatUnits(balanceWei, asset.decimals);

                    html += `
                        <div class="strategy-card" style="border-left: 4px solid #38bdf8;">
                            <div class="strategy-card-header">
                                <h3>${asset.name}</h3>
                                <span class="strategy-type-badge lending">Lent Asset</span>
                            </div>
                            <div class="strategy-metrics" style="margin-bottom:0;">
                                <div class="strategy-metric">
                                    <label>Supplied Balance</label>
                                    <span class="value" style="font-size:1.6rem;">${Number(formattedBalance).toFixed(4)} <small style="font-size:0.9rem;color:#94a3b8;">${asset.symbol}</small></span>
                                </div>
                            </div>
                            <div style="margin-top: 1rem; text-align: right;">
                                <button class="btn btn-secondary" style="font-size: 0.8rem; border-color: #ef4444; color: #ef4444;" onclick="prepareWithdraw('${asset.symbol}', '${balanceWei.toString()}')">
                                    Withdraw All
                                </button>
                            </div>
                        </div>
                    `;
                }
            } catch (err) {
                console.warn(`Could not load balance for ${asset.symbol} (${asset.address}). Contract might not be initialized on this fork.`);
            }
        }

        if (hasActivePositions) {
            container.innerHTML = html;
        } else {
            container.innerHTML = '<p class="strategy-empty">No active lending positions found in the wallet.</p>';
        }
    } catch (e) {
        console.error('Error loading portfolio:', e);
    }
}

async function prepareWithdraw(symbol, balanceWeiStr) {
    const asset = PORTFOLIO_ASSETS.find(a => a.symbol === symbol);
    if (!asset || !asset.withdrawCall) return;

    try {
        const poolAddress = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"; // AAVE_POOL address
        const uAssetAddress = asset.symbol === "aWETH" ? "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" : // WETH
            asset.symbol === "aUSDC" ? "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" : // USDC
                asset.symbol === "aWBTC" ? "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599" : // WBTC
                    ""; // Not fully mapped for all, but enough for POC

        const iface = new ethers.utils.Interface(asset.withdrawCall.abi);
        let calldata = "0x";

        // Setup calldata dynamically based on the target protocol
        if (asset.symbol === "aWETH") {
            // WETH Gateway args: address pool, uint256 amount, address to
            calldata = iface.encodeFunctionData("withdrawETH", [poolAddress, ethers.constants.MaxUint256, contract.address]);
        } else if (asset.symbol.startsWith("a")) {
            // Aave V3 general args: address asset, uint256 amount, address to
            calldata = iface.encodeFunctionData("withdraw", [uAssetAddress, ethers.constants.MaxUint256, contract.address]);
        } else if (asset.symbol === "cUSDCv3") {
            const cometAssetAddress = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"; // Withdraw USDC from comet
            calldata = iface.encodeFunctionData("withdraw", [cometAssetAddress, ethers.constants.MaxUint256]);
        }

        // Mock a strategy object to load in the form
        const dummyStrategy = {
            strategy_type: 'withdraw',
            protocol_address: asset.withdrawCall.protocol,
            token_in: asset.withdrawCall.tokenIn,
            amount_suggestion_wei: ethers.constants.MaxUint256.toString(), // Approve Max if needed
            calldata: calldata,
            description: `Withdraw entire ${asset.symbol} balance from ${asset.name} back to Multisig.`,
            eth_value: "0"
        };

        createProposalFromStrategy(dummyStrategy);
        showToast('Created withdrawal proposal. Review in Create tab.', 'info');

    } catch (e) {
        console.error("Error formatting withdraw call:", e);
        showToast("Error building withdrawal proposal", "error");
    }
}

// ============================================================
// PROPOSALS
// ============================================================

async function loadProposals() {
    if (!contract) return;
    try {
        const count = await contract.getProposalCount();
        const threshold = await contract.threshold();
        const pList = document.getElementById('proposalsList');
        const hList = document.getElementById('historyList');
        pList.innerHTML = '';
        hList.innerHTML = '';

        let hasPending = false, hasHistory = false;

        for (let i = 0; i < count; i++) {
            const p = await contract.getProposal(i);
            const hasApproved = await contract.hasApproved(i, currentAccount);
            if (!p.executed) {
                hasPending = true;
                pList.appendChild(createProposalCard(i, p, threshold, hasApproved));
            } else {
                hasHistory = true;
                hList.appendChild(createHistoryItem(i, p));
            }
        }

        if (!hasPending) pList.innerHTML = '<p class="empty-state">No pending proposals</p>';
        if (!hasHistory) hList.innerHTML = '<p class="empty-state">No transaction history</p>';
    } catch (e) {
        console.error('Error loading proposals:', e);
    }
}

function proposalTypeLabel(proposalType, strategyType) {
    if (proposalType === 0) return { label: 'Transfer', cls: 'transfer' };
    if (strategyType === 1) return { label: 'Lending', cls: 'lending' };
    if (strategyType === 2) return { label: 'Arbitrage', cls: 'arbitrage' };
    return { label: 'Strategy', cls: 'strategy' };
}

function createProposalCard(id, proposal, threshold, hasApproved) {
    const { label, cls } = proposalTypeLabel(proposal.proposalType, proposal.strategyType);
    const card = document.createElement('div');
    card.className = 'proposal-card';
    card.innerHTML = `
        <div class="proposal-header">
            <span class="proposal-id">Proposal #${id}</span>
            <span class="proposal-type ${cls}">${label}</span>
        </div>
        <div class="proposal-details">
            <p><span class="label">To:</span> <span class="value">${proposal.to}</span></p>
            <p><span class="label">Amount:</span> <span class="value">${ethers.utils.formatEther(proposal.value)} ETH</span></p>
            <p><span class="label">Description:</span> <span class="value">${proposal.description}</span></p>
        </div>
        <div class="proposal-progress">
            <span class="label">Approvals: ${proposal.approvalCount}/${threshold}</span>
            <div class="progress-bar">
                <div class="progress-fill" style="width:${(proposal.approvalCount / threshold) * 100}%"></div>
            </div>
        </div>
        <div class="proposal-actions">
            ${isAdmin && !hasApproved
            ? `<button class="btn btn-primary btn-small" onclick="approveProposal(${id})">Approve</button>`
            : hasApproved ? '<span class="badge admin">Approved</span>' : ''}
            ${isAdmin && proposal.approvalCount >= threshold - 1
            ? `<button class="btn btn-secondary btn-small" onclick="executeProposal(${id})">Execute</button>`
            : ''}
        </div>
    `;
    return card;
}

function createHistoryItem(id, proposal) {
    const { label } = proposalTypeLabel(proposal.proposalType, proposal.strategyType);
    const item = document.createElement('div');
    item.className = 'history-item';
    item.innerHTML = `
        <div>
            <strong>Proposal #${id}</strong> — ${label}
            <br>
            <small>${ethers.utils.formatEther(proposal.value)} ETH | ${proposal.description}</small>
        </div>
        <span class="status executed">Executed</span>
    `;
    return item;
}

// ============================================================
// PROPOSAL CREATION
// ============================================================

function handleProposalTypeChange() {
    const type = document.getElementById('proposalType').value;
    document.getElementById('transferFields').style.display =
        type === 'transfer' ? 'block' : 'none';
    document.getElementById('strategyFields').style.display =
        type !== 'transfer' ? 'block' : 'none';
    document.getElementById('amountGroup').style.display =
        type === 'transfer' ? 'block' : 'none';
}

async function createProposal() {
    if (!isAdmin) { showToast('Only admins can create proposals', 'error'); return; }

    const type = document.getElementById('proposalType').value;
    const description = document.getElementById('description').value;

    if (!description) { showToast('Please enter a description', 'error'); return; }

    try {
        let tx;

        if (type === 'transfer') {
            const amount = document.getElementById('amount').value;
            const recipient = document.getElementById('recipient').value;
            if (!amount || parseFloat(amount) <= 0) {
                showToast('Please enter a valid amount', 'error'); return;
            }
            if (!ethers.utils.isAddress(recipient)) {
                showToast('Please enter a valid recipient address', 'error'); return;
            }
            tx = await contract.propose(
                recipient,
                ethers.utils.parseEther(amount),
                "0x",
                description
            );

        } else {
            // Strategy proposal (lending or arbitrage)
            const protocol = document.getElementById('strategyProtocol').value;
            const tokenIn = document.getElementById('strategyTokenIn').value;
            const amountIn = document.getElementById('strategyAmountIn').value || "0";
            const calldata = document.getElementById('strategyCalldata').value || "0x";

            // Look for a hidden ethValue input, default to 0
            const ethValueInput = document.getElementById('strategyEthValue');
            const ethValue = ethValueInput ? ethValueInput.value : "0";

            if (!ethers.utils.isAddress(protocol)) {
                showToast('Please enter a valid protocol address', 'error'); return;
            }
            // Map "withdraw" -> LENDING (1) for the smart contract StrategyType Enum
            const sType = (type === 'lending' || type === 'withdraw')
                ? StrategyType.LENDING
                : StrategyType.ARBITRAGE;

            const tokenInAddr = ethers.utils.isAddress(tokenIn)
                ? tokenIn
                : ethers.constants.AddressZero;

            tx = await contract.proposeStrategy(
                protocol,
                ethValue,    // Pass the actual ethValue instead of 0
                calldata,
                description,
                sType,
                tokenInAddr,
                amountIn
            );
        }

        showToast('Transaction submitted. Waiting for confirmation...', 'info');
        await tx.wait();
        showToast('Proposal created successfully!', 'success');

        // Reset form
        document.getElementById('recipient').value = '';
        document.getElementById('amount').value = '';
        document.getElementById('description').value = '';
        document.getElementById('strategyProtocol').value = '';
        document.getElementById('strategyTokenIn').value = '';
        document.getElementById('strategyAmountIn').value = '';
        document.getElementById('strategyCalldata').value = '';

        const ethValueInput = document.getElementById('strategyEthValue');
        if (ethValueInput) ethValueInput.value = '0';

        await loadDashboardData();
        await loadProposals();
        switchTab('proposals');

    } catch (error) {
        console.error('Error creating proposal:', error);
        showToast('Failed to create proposal: ' + shortError(error.message), 'error');
    }
}

async function approveProposal(id) {
    if (!isAdmin) { showToast('Only admins can approve proposals', 'error'); return; }
    try {
        const tx = await contract.approve(id);
        showToast('Approval submitted...', 'info');
        await tx.wait();
        showToast('Proposal approved!', 'success');
        await loadDashboardData();
        await loadProposals();
    } catch (e) {
        showToast('Failed to approve: ' + shortError(e.message), 'error');
    }
}

async function executeProposal(id) {
    if (!isAdmin) { showToast('Only admins can execute proposals', 'error'); return; }
    try {
        const tx = await contract.execute(id);
        showToast('Execution submitted...', 'info');
        await tx.wait();
        showToast('Proposal executed!', 'success');
        await loadDashboardData();
        await loadProposals();
    } catch (e) {
        showToast('Failed to execute: ' + shortError(e.message), 'error');
    }
}

window.approveProposal = approveProposal;
window.executeProposal = executeProposal;

// ============================================================
// INVESTMENT STRATEGIES (backend)
// ============================================================

async function loadStrategies() {
    const lendingEl = document.getElementById('lendingStrategies');
    const arbitrageEl = document.getElementById('arbitrageStrategies');
    lendingEl.innerHTML = '<p class="strategy-empty">Loading...</p>';
    arbitrageEl.innerHTML = '<p class="strategy-empty">Loading...</p>';

    try {
        const res = await fetch(`${BACKEND_URL}/api/strategies/opportunities`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        renderStrategies(lendingEl, data.lending, 'No lending opportunities found right now.');
        renderStrategies(arbitrageEl, data.arbitrage, 'No arbitrage opportunities found right now.');

    } catch (e) {
        const msg = `<p class="strategy-empty">Could not reach the strategy backend.<br>
                     <small>Make sure <code>uvicorn main:app --reload --port 8000</code> is running.</small></p>`;
        lendingEl.innerHTML = msg;
        arbitrageEl.innerHTML = msg;
    }
}

function renderStrategies(container, strategies, emptyMsg) {
    if (!strategies || strategies.length === 0) {
        container.innerHTML = `<p class="strategy-empty">${emptyMsg}</p>`;
        return;
    }
    container.innerHTML = '';
    strategies.forEach(s => container.appendChild(createStrategyCard(s)));
}

function createStrategyCard(s) {
    const now = Math.floor(Date.now() / 1000);
    const expired = s.expires_at && s.expires_at < now;
    const expLabel = expired
        ? '<span class="strategy-expires strategy-expired">Expired</span>'
        : s.expires_at
            ? `<span class="strategy-expires">Expires in ${s.expires_at - now}s</span>`
            : '';

    const typeClass = s.strategy_type === 'lending' ? 'lending' : 'arbitrage';

    const card = document.createElement('div');
    card.className = 'strategy-card';
    card.innerHTML = `
        <div class="strategy-card-header">
            <h3>${s.protocol_name}</h3>
            <span class="strategy-type-badge ${typeClass}">${s.strategy_type}</span>
        </div>
        <div class="strategy-metrics">
            <div class="strategy-metric">
                <label>Est. Return</label>
                <span class="value">${s.expected_return_pct.toFixed(2)}%</span>
            </div>
            <div class="strategy-metric">
                <label>Risk</label>
                <span class="value risk-${s.risk_score}">${s.risk_score}/10</span>
            </div>
            <div class="strategy-metric">
                <label>Token In</label>
                <span class="value" style="font-size:0.9rem;">${s.token_in_symbol}</span>
            </div>
        </div>
        <p class="strategy-desc">${s.description}</p>
        <div class="strategy-footer">
            ${expLabel}
            ${isAdmin && !expired
            ? `<button class="btn btn-primary btn-small"
                       onclick='createProposalFromStrategy(${JSON.stringify(s)})'>
                       Create Proposal
                   </button>`
            : '<span></span>'}
        </div>
    `;
    return card;
}

/**
 * Pre-fill the Create Proposal form from a strategy recommendation
 * and switch to that tab.
 */
function createProposalFromStrategy(strategy) {
    // Switch to create tab
    switchTab('create');

    // Set proposal type
    const typeSelect = document.getElementById('proposalType');
    if (strategy.strategy_type === 'lending') typeSelect.value = 'lending';
    else if (strategy.strategy_type === 'withdraw') typeSelect.value = 'withdraw';
    else typeSelect.value = 'arbitrage';

    handleProposalTypeChange();

    // Fill strategy fields
    document.getElementById('strategyProtocol').value = strategy.protocol_address;
    document.getElementById('strategyTokenIn').value = strategy.token_in;
    document.getElementById('strategyAmountIn').value = strategy.amount_suggestion_wei;
    document.getElementById('strategyCalldata').value = strategy.calldata;
    document.getElementById('description').value = strategy.description;

    // Build human-readable helper texts
    let amountInHelper = document.getElementById('strategyAmountInHelper');
    if (!amountInHelper) {
        amountInHelper = document.createElement('small');
        amountInHelper.id = 'strategyAmountInHelper';
        amountInHelper.style.display = 'block';
        amountInHelper.style.color = '#10b981'; // Green readable text
        amountInHelper.style.marginTop = '4px';
        document.getElementById('strategyAmountIn').parentNode.appendChild(amountInHelper);
    }

    // Guess decimals based on token_in address (not robust but works for our testnet)
    const isUSDC = strategy.token_in && strategy.token_in.toLowerCase() === "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48";
    const decimals = isUSDC ? 6 : (strategy.token_in === ethers.constants.AddressZero ? 18 : 18); // Default 18
    const readableAmount = ethers.utils.formatUnits(strategy.amount_suggestion_wei || "0", decimals);

    amountInHelper.innerText = `≈ ${readableAmount} tokens`;

    // Handle ethValue
    let ethValueInput = document.getElementById('strategyEthValue');
    if (!ethValueInput) {
        ethValueInput = document.createElement('input');
        ethValueInput.type = 'hidden';
        ethValueInput.id = 'strategyEthValue';
        document.getElementById('strategyFields').appendChild(ethValueInput);
    }
    ethValueInput.value = strategy.eth_value || "0";

    // readable helper for ethValue too
    let ethValueHelper = document.getElementById('strategyEthHelper');
    if (!ethValueHelper) {
        ethValueHelper = document.createElement('small');
        ethValueHelper.id = 'strategyEthHelper';
        ethValueHelper.style.display = 'block';
        ethValueHelper.style.color = '#38bdf8'; // Blue readable text
        ethValueHelper.style.marginTop = '4px';
        document.getElementById('strategyProtocol').parentNode.appendChild(ethValueHelper);
    }
    ethValueHelper.innerText = strategy.eth_value && strategy.eth_value !== "0"
        ? `+ Sending ${ethers.utils.formatEther(strategy.eth_value)} natively attached ETH`
        : '';

    showToast('Strategy pre-loaded into the form. Review and submit.', 'info');
}

window.createProposalFromStrategy = createProposalFromStrategy;

// ============================================================
// CONTRACT EVENTS
// ============================================================

function setupContractEvents() {
    contract.on('ProposalCreated', async (txId) => {
        await loadDashboardData();
        await loadProposals();
        showToast(`New proposal #${txId} created`, 'info');
    });

    contract.on('Approved', async (admin, txId) => {
        await loadProposals();
        if (admin.toLowerCase() !== currentAccount) {
            showToast(`Proposal #${txId} approved by ${admin.slice(0, 8)}...`, 'info');
        }
    });

    contract.on('Executed', async (txId) => {
        await loadDashboardData();
        await loadProposals();
        showToast(`Proposal #${txId} executed!`, 'success');
    });

    contract.on('Deposit', async (sender, amount) => {
        await loadDashboardData();
        showToast(`Received ${ethers.utils.formatEther(amount)} ETH from ${sender.slice(0, 8)}...`, 'success');
    });

    contract.on('StrategyExecuted', async (txId, strategyType, protocol) => {
        const names = { 0: 'None', 1: 'Lending', 2: 'Arbitrage' };
        showToast(`Strategy executed: ${names[strategyType] || strategyType} on ${protocol.slice(0, 8)}...`, 'success');
        await loadPortfolio();
    });
}

// ============================================================
// UI HELPERS
// ============================================================

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.toggle('active', el.id === tabId);
    });
}

function shortError(msg) {
    if (!msg) return 'Unknown error';
    // Extract revert reason if present
    const revertMatch = msg.match(/execution reverted: ([^"\\(]+)/);
    if (revertMatch) return revertMatch[1].trim();
    // Truncate long messages
    return msg.length > 80 ? msg.slice(0, 80) + '…' : msg;
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}
