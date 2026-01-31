// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MultisigWallet
 * @notice A multi-signature wallet for group fund management
 * @dev Requires threshold number of admin approvals before executing transactions
 */
contract MultisigWallet {
    // Events
    event Deposit(address indexed sender, uint256 amount, uint256 balance);
    event ProposalCreated(uint256 indexed txId, address indexed proposer, address indexed to, uint256 value, bytes data, string description);
    event Approved(address indexed admin, uint256 indexed txId);
    event Executed(uint256 indexed txId);
    event AdminAdded(address indexed admin);
    event AdminRemoved(address indexed admin);
    event ThresholdChanged(uint256 oldThreshold, uint256 newThreshold);

    // Structs
    struct Proposal {
        address to;
        uint256 value;
        bytes data;
        string description;
        bool executed;
        uint256 approvalCount;
    }

    // State variables
    address[] public admins;
    mapping(address => bool) public isAdmin;
    uint256 public threshold;

    Proposal[] public proposals;
    mapping(uint256 => mapping(address => bool)) public hasApproved;

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
     * @notice Initialize the multisig wallet with admins and threshold
     * @param _admins Array of admin addresses
     * @param _threshold Number of required approvals
     */
    constructor(address[] memory _admins, uint256 _threshold) {
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
    }

    /**
     * @notice Receive ETH deposits
     */
    receive() external payable {
        emit Deposit(msg.sender, msg.value, address(this).balance);
    }

    /**
     * @notice Fallback function to receive ETH
     */
    fallback() external payable {
        emit Deposit(msg.sender, msg.value, address(this).balance);
    }

    /**
     * @notice Create a new proposal to send funds
     * @param _to Recipient address
     * @param _value Amount of ETH to send (in wei)
     * @param _data Additional calldata
     * @param _description Description of the proposal
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
            approvalCount: 0
        }));

        emit ProposalCreated(txId, msg.sender, _to, _value, _data, _description);
        return txId;
    }

    /**
     * @notice Approve a proposal
     * @param _txId Transaction/Proposal ID
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
     * @notice Execute a proposal after sufficient approvals
     * @param _txId Transaction/Proposal ID
     */
    function execute(uint256 _txId)
        external
        onlyAdmin
        txExists(_txId)
        notExecuted(_txId)
    {
        Proposal storage proposal = proposals[_txId];

        // If caller hasn't approved yet, count this as approval
        if (!hasApproved[_txId][msg.sender]) {
            hasApproved[_txId][msg.sender] = true;
            proposal.approvalCount++;
            emit Approved(msg.sender, _txId);
        }

        require(proposal.approvalCount >= threshold, "Not enough approvals");

        proposal.executed = true;

        (bool success, ) = proposal.to.call{value: proposal.value}(proposal.data);
        require(success, "Transaction execution failed");

        emit Executed(_txId);
    }

    /**
     * @notice Get the number of admins
     */
    function getAdminCount() external view returns (uint256) {
        return admins.length;
    }

    /**
     * @notice Get all admins
     */
    function getAdmins() external view returns (address[] memory) {
        return admins;
    }

    /**
     * @notice Get proposal count
     */
    function getProposalCount() external view returns (uint256) {
        return proposals.length;
    }

    /**
     * @notice Get proposal details
     * @param _txId Transaction/Proposal ID
     */
    function getProposal(uint256 _txId) external view returns (
        address to,
        uint256 value,
        bytes memory data,
        string memory description,
        bool executed,
        uint256 approvalCount
    ) {
        Proposal storage proposal = proposals[_txId];
        return (
            proposal.to,
            proposal.value,
            proposal.data,
            proposal.description,
            proposal.executed,
            proposal.approvalCount
        );
    }

    /**
     * @notice Check if a proposal can be executed
     * @param _txId Transaction/Proposal ID
     */
    function canExecute(uint256 _txId) external view returns (bool) {
        if (_txId >= proposals.length) return false;
        Proposal storage proposal = proposals[_txId];
        return !proposal.executed && proposal.approvalCount >= threshold;
    }

    /**
     * @notice Get wallet balance
     */
    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }
}
