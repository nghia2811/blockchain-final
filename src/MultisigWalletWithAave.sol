// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./interfaces/IAavePool.sol";
import "./interfaces/IWETH.sol";
import "./interfaces/IERC20.sol";

/**
 * @title MultisigWalletWithAave
 * @notice Multi-signature wallet with Aave integration for yield farming
 * @dev Combines multisig security with DeFi yield generation
 */
contract MultisigWalletWithAave {
    // Events
    event Deposit(address indexed sender, uint256 amount, uint256 balance);
    event ProposalCreated(uint256 indexed txId, address indexed proposer, address indexed to, uint256 value, bytes data, string description);
    event Approved(address indexed admin, uint256 indexed txId);
    event Executed(uint256 indexed txId);
    event AdminAdded(address indexed admin);
    event AdminRemoved(address indexed admin);
    event ThresholdChanged(uint256 oldThreshold, uint256 newThreshold);
    event DepositedToAave(address indexed asset, uint256 amount);
    event WithdrawnFromAave(address indexed asset, uint256 amount);

    // Proposal types
    enum ProposalType {
        TRANSFER,           // Regular ETH/token transfer
        AAVE_DEPOSIT,       // Deposit to Aave
        AAVE_WITHDRAW       // Withdraw from Aave
    }

    // Structs
    struct Proposal {
        address to;
        uint256 value;
        bytes data;
        string description;
        bool executed;
        uint256 approvalCount;
        ProposalType proposalType;
        address asset;      // For Aave operations
    }

    // State variables
    address[] public admins;
    mapping(address => bool) public isAdmin;
    uint256 public threshold;

    Proposal[] public proposals;
    mapping(uint256 => mapping(address => bool)) public hasApproved;

    // Aave integration
    IAavePool public aavePool;
    IWETH public weth;
    bool public aaveEnabled;

    // Modifiers
    modifier onlyAdmin() {
        require(isAdmin[msg.sender], "Not an admin");
        _;
    }

    modifier txExists(uint256 _txId) {
        require(_txId < proposals.length, "Transaction does not exist");
        _;
    }

    modifier notExecuted(uint256 _txId) {
        require(!proposals[_txId].executed, "Transaction already executed");
        _;
    }

    modifier notApproved(uint256 _txId) {
        require(!hasApproved[_txId][msg.sender], "Transaction already approved by you");
        _;
    }

    /**
     * @notice Initialize the multisig wallet
     * @param _admins Array of admin addresses
     * @param _threshold Number of required approvals
     * @param _aavePool Aave V3 Pool address (can be address(0) to disable)
     * @param _weth WETH address
     */
    constructor(
        address[] memory _admins,
        uint256 _threshold,
        address _aavePool,
        address _weth
    ) {
        require(_admins.length > 0, "At least one admin required");
        require(_threshold > 0 && _threshold <= _admins.length, "Invalid threshold");

        for (uint256 i = 0; i < _admins.length; i++) {
            address admin = _admins[i];
            require(admin != address(0), "Invalid admin address");
            require(!isAdmin[admin], "Duplicate admin");

            isAdmin[admin] = true;
            admins.push(admin);
            emit AdminAdded(admin);
        }

        threshold = _threshold;

        // Setup Aave integration
        if (_aavePool != address(0)) {
            aavePool = IAavePool(_aavePool);
            weth = IWETH(_weth);
            aaveEnabled = true;
        }
    }

    receive() external payable {
        emit Deposit(msg.sender, msg.value, address(this).balance);
    }

    fallback() external payable {
        emit Deposit(msg.sender, msg.value, address(this).balance);
    }

    // ========== PROPOSAL FUNCTIONS ==========

    /**
     * @notice Create a transfer proposal
     */
    function propose(
        address _to,
        uint256 _value,
        bytes calldata _data,
        string calldata _description
    ) external onlyAdmin returns (uint256) {
        require(_to != address(0), "Invalid recipient");

        uint256 txId = proposals.length;
        proposals.push(Proposal({
            to: _to,
            value: _value,
            data: _data,
            description: _description,
            executed: false,
            approvalCount: 0,
            proposalType: ProposalType.TRANSFER,
            asset: address(0)
        }));

        emit ProposalCreated(txId, msg.sender, _to, _value, _data, _description);
        return txId;
    }

    /**
     * @notice Create a proposal to deposit to Aave
     * @param _asset Asset to deposit (address(0) for ETH)
     * @param _amount Amount to deposit
     * @param _description Description
     */
    function proposeAaveDeposit(
        address _asset,
        uint256 _amount,
        string calldata _description
    ) external onlyAdmin returns (uint256) {
        require(aaveEnabled, "Aave not enabled");
        require(_amount > 0, "Amount must be > 0");

        uint256 txId = proposals.length;
        proposals.push(Proposal({
            to: address(aavePool),
            value: _amount,
            data: "",
            description: _description,
            executed: false,
            approvalCount: 0,
            proposalType: ProposalType.AAVE_DEPOSIT,
            asset: _asset
        }));

        emit ProposalCreated(txId, msg.sender, address(aavePool), _amount, "", _description);
        return txId;
    }

    /**
     * @notice Create a proposal to withdraw from Aave
     * @param _asset Asset to withdraw (address(0) for ETH)
     * @param _amount Amount to withdraw (type(uint256).max for all)
     * @param _description Description
     */
    function proposeAaveWithdraw(
        address _asset,
        uint256 _amount,
        string calldata _description
    ) external onlyAdmin returns (uint256) {
        require(aaveEnabled, "Aave not enabled");

        uint256 txId = proposals.length;
        proposals.push(Proposal({
            to: address(aavePool),
            value: _amount,
            data: "",
            description: _description,
            executed: false,
            approvalCount: 0,
            proposalType: ProposalType.AAVE_WITHDRAW,
            asset: _asset
        }));

        emit ProposalCreated(txId, msg.sender, address(aavePool), _amount, "", _description);
        return txId;
    }

    /**
     * @notice Approve a proposal
     */
    function approve(uint256 _txId)
        external
        onlyAdmin
        txExists(_txId)
        notExecuted(_txId)
        notApproved(_txId)
    {
        hasApproved[_txId][msg.sender] = true;
        proposals[_txId].approvalCount++;
        emit Approved(msg.sender, _txId);
    }

    /**
     * @notice Execute a proposal
     */
    function execute(uint256 _txId)
        external
        onlyAdmin
        txExists(_txId)
        notExecuted(_txId)
    {
        Proposal storage proposal = proposals[_txId];

        // Count this as approval if not already approved
        if (!hasApproved[_txId][msg.sender]) {
            hasApproved[_txId][msg.sender] = true;
            proposal.approvalCount++;
            emit Approved(msg.sender, _txId);
        }

        require(proposal.approvalCount >= threshold, "Not enough approvals");
        proposal.executed = true;

        // Execute based on proposal type
        if (proposal.proposalType == ProposalType.TRANSFER) {
            _executeTransfer(proposal);
        } else if (proposal.proposalType == ProposalType.AAVE_DEPOSIT) {
            _executeAaveDeposit(proposal);
        } else if (proposal.proposalType == ProposalType.AAVE_WITHDRAW) {
            _executeAaveWithdraw(proposal);
        }

        emit Executed(_txId);
    }

    function _executeTransfer(Proposal storage proposal) internal {
        (bool success, ) = proposal.to.call{value: proposal.value}(proposal.data);
        require(success, "Transfer failed");
    }

    function _executeAaveDeposit(Proposal storage proposal) internal {
        if (proposal.asset == address(0)) {
            // Deposit ETH
            _depositEthToAave(proposal.value);
        } else {
            // Deposit ERC20
            _depositERC20ToAave(proposal.asset, proposal.value);
        }
    }

    function _executeAaveWithdraw(Proposal storage proposal) internal {
        if (proposal.asset == address(0)) {
            // Withdraw ETH
            _withdrawEthFromAave();
        } else {
            // Withdraw ERC20
            _withdrawERC20FromAave(proposal.asset, proposal.value);
        }
    }

    // ========== AAVE INTERNAL FUNCTIONS ==========

    function _depositEthToAave(uint256 amount) internal {
        require(address(this).balance >= amount, "Insufficient ETH");

        // Wrap ETH to WETH
        weth.deposit{value: amount}();

        // Approve and supply to Aave
        weth.approve(address(aavePool), amount);
        aavePool.supply(address(weth), amount, address(this), 0);

        emit DepositedToAave(address(0), amount);
    }

    function _depositERC20ToAave(address asset, uint256 amount) internal {
        require(IERC20(asset).balanceOf(address(this)) >= amount, "Insufficient balance");

        // Approve and supply to Aave
        IERC20(asset).approve(address(aavePool), amount);
        aavePool.supply(asset, amount, address(this), 0);

        emit DepositedToAave(asset, amount);
    }

    function _withdrawEthFromAave() internal {
        // Withdraw WETH from Aave
        uint256 withdrawn = aavePool.withdraw(address(weth), type(uint256).max, address(this));

        if (withdrawn > 0) {
            // Unwrap WETH to ETH
            weth.withdraw(withdrawn);
        }

        emit WithdrawnFromAave(address(0), withdrawn);
    }

    function _withdrawERC20FromAave(address asset, uint256 amount) internal {
        uint256 withdrawn = aavePool.withdraw(asset, amount, address(this));
        emit WithdrawnFromAave(asset, withdrawn);
    }

    // ========== VIEW FUNCTIONS ==========

    function getAdminCount() external view returns (uint256) {
        return admins.length;
    }

    function getAdmins() external view returns (address[] memory) {
        return admins;
    }

    function getProposalCount() external view returns (uint256) {
        return proposals.length;
    }

    function getProposal(uint256 _txId) external view returns (
        address to,
        uint256 value,
        bytes memory data,
        string memory description,
        bool executed,
        uint256 approvalCount,
        ProposalType proposalType,
        address asset
    ) {
        Proposal storage p = proposals[_txId];
        return (p.to, p.value, p.data, p.description, p.executed, p.approvalCount, p.proposalType, p.asset);
    }

    function canExecute(uint256 _txId) external view returns (bool) {
        if (_txId >= proposals.length) return false;
        Proposal storage p = proposals[_txId];
        return !p.executed && p.approvalCount >= threshold;
    }

    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }

    function getAaveBalance(address aToken) external view returns (uint256) {
        if (!aaveEnabled) return 0;
        return IERC20(aToken).balanceOf(address(this));
    }

    function getAaveAccountData() external view returns (
        uint256 totalCollateralBase,
        uint256 totalDebtBase,
        uint256 availableBorrowsBase,
        uint256 currentLiquidationThreshold,
        uint256 ltv,
        uint256 healthFactor
    ) {
        require(aaveEnabled, "Aave not enabled");
        return aavePool.getUserAccountData(address(this));
    }
}
