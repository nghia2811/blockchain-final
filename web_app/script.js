// ============================================================
// Group Multisig Wallet - Frontend Script
// ============================================================

// Contract Configuration - UPDATE THESE AFTER DEPLOYMENT
const CONTRACT_ADDRESS = "YOUR_CONTRACT_ADDRESS_HERE"; // Update after deployment

// Contract ABI - Update this with the compiled ABI from forge build
const CONTRACT_ABI = [
    // Events
    "event Deposit(address indexed sender, uint256 amount, uint256 balance)",
    "event ProposalCreated(uint256 indexed txId, address indexed proposer, address indexed to, uint256 value, bytes data, string description)",
    "event Approved(address indexed admin, uint256 indexed txId)",
    "event Executed(uint256 indexed txId)",
    "event DepositedToAave(address indexed asset, uint256 amount)",
    "event WithdrawnFromAave(address indexed asset, uint256 amount)",

    // Read Functions
    "function admins(uint256) view returns (address)",
    "function isAdmin(address) view returns (bool)",
    "function threshold() view returns (uint256)",
    "function proposals(uint256) view returns (address to, uint256 value, bytes data, string description, bool executed, uint256 approvalCount, uint8 proposalType, address asset)",
    "function hasApproved(uint256, address) view returns (bool)",
    "function getAdminCount() view returns (uint256)",
    "function getAdmins() view returns (address[])",
    "function getProposalCount() view returns (uint256)",
    "function getProposal(uint256) view returns (address to, uint256 value, bytes data, string description, bool executed, uint256 approvalCount, uint8 proposalType, address asset)",
    "function canExecute(uint256) view returns (bool)",
    "function getBalance() view returns (uint256)",
    "function getAaveBalance(address) view returns (uint256)",
    "function aaveEnabled() view returns (bool)",

    // Write Functions
    "function propose(address _to, uint256 _value, bytes _data, string _description) returns (uint256)",
    "function proposeAaveDeposit(address _asset, uint256 _amount, string _description) returns (uint256)",
    "function proposeAaveWithdraw(address _asset, uint256 _amount, string _description) returns (uint256)",
    "function approve(uint256 _txId)",
    "function execute(uint256 _txId)"
];

// Aave aWETH address on mainnet (for checking Aave balance)
const AWETH_ADDRESS = "0x4d5F47FA6A74757f35C14fD3a6Ef8E3C9BC514E8";

// Global State
let provider;
let signer;
let contract;
let currentAccount;
let isAdmin = false;

// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
});

async function initializeApp() {
    // Check if MetaMask is installed
    if (typeof window.ethereum !== 'undefined') {
        console.log('MetaMask is installed!');

        // Check if already connected
        const accounts = await window.ethereum.request({ method: 'eth_accounts' });
        if (accounts.length > 0) {
            await connectWallet();
        }

        // Listen for account changes
        window.ethereum.on('accountsChanged', handleAccountsChanged);
        window.ethereum.on('chainChanged', () => window.location.reload());
    } else {
        showToast('Please install MetaMask to use this DApp', 'error');
    }
}

function setupEventListeners() {
    // Connect wallet button
    document.getElementById('connectBtn').addEventListener('click', connectWallet);

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Create proposal
    document.getElementById('createProposalBtn').addEventListener('click', createProposal);

    // Proposal type change
    document.getElementById('proposalType').addEventListener('change', handleProposalTypeChange);

    // Quick deposit/withdraw buttons
    document.getElementById('quickDepositBtn').addEventListener('click', () => {
        switchTab('create');
        document.getElementById('proposalType').value = 'aaveDeposit';
        handleProposalTypeChange();
    });

    document.getElementById('quickWithdrawBtn').addEventListener('click', () => {
        switchTab('create');
        document.getElementById('proposalType').value = 'aaveWithdraw';
        handleProposalTypeChange();
    });
}

// ============================================================
// WALLET CONNECTION
// ============================================================

async function connectWallet() {
    try {
        // Request account access
        const accounts = await window.ethereum.request({
            method: 'eth_requestAccounts'
        });

        currentAccount = accounts[0].toLowerCase();

        // Setup ethers provider and signer
        provider = new ethers.providers.Web3Provider(window.ethereum);
        signer = provider.getSigner();

        // Connect to contract
        contract = new ethers.Contract(CONTRACT_ADDRESS, CONTRACT_ABI, signer);

        // Update UI
        await updateAccountUI();
        await loadDashboardData();
        await loadProposals();

        // Setup event listeners for contract
        setupContractEvents();

        showToast('Wallet connected successfully!', 'success');
    } catch (error) {
        console.error('Error connecting wallet:', error);
        showToast('Failed to connect wallet: ' + error.message, 'error');
    }
}

async function handleAccountsChanged(accounts) {
    if (accounts.length === 0) {
        // User disconnected
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
    const connectBtn = document.getElementById('connectBtn');
    const accountInfo = document.getElementById('accountInfo');
    const accountAddress = document.getElementById('accountAddress');
    const accountRole = document.getElementById('accountRole');

    connectBtn.classList.add('hidden');
    accountInfo.classList.remove('hidden');

    // Truncate address
    accountAddress.textContent = `${currentAccount.slice(0, 6)}...${currentAccount.slice(-4)}`;

    // Check if admin
    try {
        isAdmin = await contract.isAdmin(currentAccount);
        accountRole.textContent = isAdmin ? 'Admin' : 'Guest';
        accountRole.className = `badge ${isAdmin ? 'admin' : 'guest'}`;
    } catch (error) {
        console.error('Error checking admin status:', error);
        accountRole.textContent = 'Unknown';
    }
}

// ============================================================
// DATA LOADING
// ============================================================

async function loadDashboardData() {
    try {
        // Load wallet balance
        const balance = await contract.getBalance();
        document.getElementById('walletBalance').textContent =
            `${ethers.utils.formatEther(balance)} ETH`;

        // Load threshold info
        const threshold = await contract.threshold();
        const adminCount = await contract.getAdminCount();
        document.getElementById('thresholdInfo').textContent = `${threshold}/${adminCount}`;

        // Load admins
        const admins = await contract.getAdmins();
        displayAdmins(admins);

        // Load pending proposals count
        const proposalCount = await contract.getProposalCount();
        let pendingCount = 0;
        for (let i = 0; i < proposalCount; i++) {
            const proposal = await contract.getProposal(i);
            if (!proposal.executed) pendingCount++;
        }
        document.getElementById('pendingCount').textContent = pendingCount;

        // Load Aave balance (if enabled)
        try {
            const aaveEnabled = await contract.aaveEnabled();
            if (aaveEnabled) {
                const aaveBalance = await contract.getAaveBalance(AWETH_ADDRESS);
                document.getElementById('aaveBalance').textContent =
                    `${ethers.utils.formatEther(aaveBalance)} ETH`;
                document.getElementById('currentDeposit').textContent =
                    `${ethers.utils.formatEther(aaveBalance)} ETH`;
            }
        } catch (error) {
            console.log('Aave not enabled or error loading balance');
        }
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        showToast('Error loading dashboard data', 'error');
    }
}

function displayAdmins(admins) {
    const adminsList = document.getElementById('adminsList');
    adminsList.innerHTML = '';

    admins.forEach(admin => {
        const adminBadge = document.createElement('div');
        adminBadge.className = `admin-badge ${admin.toLowerCase() === currentAccount ? 'current' : ''}`;
        adminBadge.textContent = `${admin.slice(0, 6)}...${admin.slice(-4)}`;
        adminsList.appendChild(adminBadge);
    });
}

async function loadProposals() {
    try {
        const proposalCount = await contract.getProposalCount();
        const proposalsList = document.getElementById('proposalsList');
        const historyList = document.getElementById('historyList');

        proposalsList.innerHTML = '';
        historyList.innerHTML = '';

        let hasPending = false;
        let hasHistory = false;

        const threshold = await contract.threshold();

        for (let i = 0; i < proposalCount; i++) {
            const proposal = await contract.getProposal(i);
            const hasApproved = await contract.hasApproved(i, currentAccount);

            if (!proposal.executed) {
                hasPending = true;
                proposalsList.appendChild(createProposalCard(i, proposal, threshold, hasApproved));
            } else {
                hasHistory = true;
                historyList.appendChild(createHistoryItem(i, proposal));
            }
        }

        if (!hasPending) {
            proposalsList.innerHTML = '<p class="empty-state">No pending proposals</p>';
        }
        if (!hasHistory) {
            historyList.innerHTML = '<p class="empty-state">No transaction history</p>';
        }
    } catch (error) {
        console.error('Error loading proposals:', error);
    }
}

function createProposalCard(id, proposal, threshold, hasApproved) {
    const proposalTypes = ['Transfer', 'Aave Deposit', 'Aave Withdraw'];
    const typeClasses = ['transfer', 'deposit', 'withdraw'];
    const typeIndex = proposal.proposalType;

    const card = document.createElement('div');
    card.className = 'proposal-card';
    card.innerHTML = `
        <div class="proposal-header">
            <span class="proposal-id">Proposal #${id}</span>
            <span class="proposal-type ${typeClasses[typeIndex]}">${proposalTypes[typeIndex]}</span>
        </div>
        <div class="proposal-details">
            <p><span class="label">To:</span> <span class="value">${proposal.to}</span></p>
            <p><span class="label">Amount:</span> <span class="value">${ethers.utils.formatEther(proposal.value)} ETH</span></p>
            <p><span class="label">Description:</span> <span class="value">${proposal.description}</span></p>
        </div>
        <div class="proposal-progress">
            <span class="label">Approvals: ${proposal.approvalCount}/${threshold}</span>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${(proposal.approvalCount / threshold) * 100}%"></div>
            </div>
        </div>
        <div class="proposal-actions">
            ${isAdmin && !hasApproved ?
                `<button class="btn btn-primary btn-small" onclick="approveProposal(${id})">Approve</button>` :
                hasApproved ? '<span class="badge admin">Approved</span>' : ''}
            ${isAdmin && proposal.approvalCount >= threshold - 1 ?
                `<button class="btn btn-secondary btn-small" onclick="executeProposal(${id})">Execute</button>` : ''}
        </div>
    `;
    return card;
}

function createHistoryItem(id, proposal) {
    const proposalTypes = ['Transfer', 'Aave Deposit', 'Aave Withdraw'];
    const item = document.createElement('div');
    item.className = 'history-item';
    item.innerHTML = `
        <div>
            <strong>Proposal #${id}</strong> - ${proposalTypes[proposal.proposalType]}
            <br>
            <small>${ethers.utils.formatEther(proposal.value)} ETH to ${proposal.to.slice(0, 10)}...</small>
        </div>
        <span class="status executed">Executed</span>
    `;
    return item;
}

// ============================================================
// PROPOSAL ACTIONS
// ============================================================

function handleProposalTypeChange() {
    const type = document.getElementById('proposalType').value;
    const transferFields = document.getElementById('transferFields');

    if (type === 'transfer') {
        transferFields.style.display = 'block';
    } else {
        transferFields.style.display = 'none';
    }
}

async function createProposal() {
    if (!isAdmin) {
        showToast('Only admins can create proposals', 'error');
        return;
    }

    const type = document.getElementById('proposalType').value;
    const amount = document.getElementById('amount').value;
    const description = document.getElementById('description').value;

    if (!amount || parseFloat(amount) <= 0) {
        showToast('Please enter a valid amount', 'error');
        return;
    }

    if (!description) {
        showToast('Please enter a description', 'error');
        return;
    }

    try {
        let tx;
        const amountWei = ethers.utils.parseEther(amount);

        if (type === 'transfer') {
            const recipient = document.getElementById('recipient').value;
            if (!ethers.utils.isAddress(recipient)) {
                showToast('Please enter a valid recipient address', 'error');
                return;
            }
            tx = await contract.propose(recipient, amountWei, "0x", description);
        } else if (type === 'aaveDeposit') {
            tx = await contract.proposeAaveDeposit(ethers.constants.AddressZero, amountWei, description);
        } else if (type === 'aaveWithdraw') {
            tx = await contract.proposeAaveWithdraw(ethers.constants.AddressZero, amountWei, description);
        }

        showToast('Transaction submitted. Waiting for confirmation...', 'info');
        await tx.wait();

        showToast('Proposal created successfully!', 'success');

        // Clear form
        document.getElementById('recipient').value = '';
        document.getElementById('amount').value = '';
        document.getElementById('description').value = '';

        // Reload data
        await loadDashboardData();
        await loadProposals();

        // Switch to proposals tab
        switchTab('proposals');
    } catch (error) {
        console.error('Error creating proposal:', error);
        showToast('Failed to create proposal: ' + error.message, 'error');
    }
}

async function approveProposal(id) {
    if (!isAdmin) {
        showToast('Only admins can approve proposals', 'error');
        return;
    }

    try {
        const tx = await contract.approve(id);
        showToast('Approval submitted. Waiting for confirmation...', 'info');
        await tx.wait();

        showToast('Proposal approved successfully!', 'success');
        await loadDashboardData();
        await loadProposals();
    } catch (error) {
        console.error('Error approving proposal:', error);
        showToast('Failed to approve: ' + error.message, 'error');
    }
}

async function executeProposal(id) {
    if (!isAdmin) {
        showToast('Only admins can execute proposals', 'error');
        return;
    }

    try {
        const tx = await contract.execute(id);
        showToast('Execution submitted. Waiting for confirmation...', 'info');
        await tx.wait();

        showToast('Proposal executed successfully!', 'success');
        await loadDashboardData();
        await loadProposals();
    } catch (error) {
        console.error('Error executing proposal:', error);
        showToast('Failed to execute: ' + error.message, 'error');
    }
}

// Make functions globally accessible
window.approveProposal = approveProposal;
window.executeProposal = executeProposal;

// ============================================================
// CONTRACT EVENTS
// ============================================================

function setupContractEvents() {
    // Listen for new proposals
    contract.on('ProposalCreated', async (txId, proposer, to, value, data, description) => {
        console.log('New proposal created:', txId.toString());
        await loadDashboardData();
        await loadProposals();
        showToast(`New proposal #${txId} created`, 'info');
    });

    // Listen for approvals
    contract.on('Approved', async (admin, txId) => {
        console.log('Proposal approved:', txId.toString(), 'by', admin);
        await loadProposals();
        if (admin.toLowerCase() !== currentAccount) {
            showToast(`Proposal #${txId} was approved by ${admin.slice(0, 8)}...`, 'info');
        }
    });

    // Listen for executions
    contract.on('Executed', async (txId) => {
        console.log('Proposal executed:', txId.toString());
        await loadDashboardData();
        await loadProposals();
        showToast(`Proposal #${txId} was executed!`, 'success');
    });

    // Listen for deposits
    contract.on('Deposit', async (sender, amount, balance) => {
        console.log('Deposit received:', ethers.utils.formatEther(amount), 'ETH');
        await loadDashboardData();
        showToast(`Received ${ethers.utils.formatEther(amount)} ETH from ${sender.slice(0, 8)}...`, 'success');
    });
}

// ============================================================
// UI HELPERS
// ============================================================

function switchTab(tabId) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === tabId);
    });
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

// Helper function to get all users who have sent or received IOUs
async function getUsers() {
    const users = new Set();
    const admins = await contract.getAdmins();
    admins.forEach(admin => users.add(admin.toLowerCase()));
    return Array.from(users);
}

// Helper function to get total owed by a user
async function getTotalOwed(user) {
    // This would require tracking debt in the contract
    // For this implementation, we focus on multisig features
    return 0;
}

// ============================================================
// SANITY CHECK (for testing)
// ============================================================

async function sanityCheck() {
    console.log("=== Starting Sanity Check ===");

    try {
        // Check contract connection
        console.log("Contract address:", CONTRACT_ADDRESS);

        // Check admin count
        const adminCount = await contract.getAdminCount();
        console.log("Admin count:", adminCount.toString());

        // Check threshold
        const threshold = await contract.threshold();
        console.log("Threshold:", threshold.toString());

        // Check balance
        const balance = await contract.getBalance();
        console.log("Balance:", ethers.utils.formatEther(balance), "ETH");

        // Check current account admin status
        const isAdminStatus = await contract.isAdmin(currentAccount);
        console.log("Current account is admin:", isAdminStatus);

        console.log("=== Sanity Check Passed ===");
        return true;
    } catch (error) {
        console.error("Sanity check failed:", error);
        return false;
    }
}

// Expose sanityCheck for console access
window.sanityCheck = sanityCheck;
