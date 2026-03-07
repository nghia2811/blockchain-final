// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./interfaces/IERC20.sol";
import "./interfaces/IChainlinkAggregator.sol";

/**
 * @title MultisigWalletWithStrategies
 * @notice Multi-signature wallet with flexible investment strategy execution.
 *         A Python backend analyses Chainlink prices and generates strategy
 *         proposals (lending / arbitrage).  Admins review, approve, and
 *         execute them through the standard multisig flow.
 */
contract MultisigWalletWithStrategies {
    // -------------------------------------------------------------------------
    // Enums
    // -------------------------------------------------------------------------

    enum ProposalType {
        TRANSFER,
        STRATEGY
    }
    enum StrategyType {
        NONE,
        LENDING,
        ARBITRAGE
    }

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    event Deposit(address indexed sender, uint256 amount, uint256 balance);
    event ProposalCreated(
        uint256 indexed txId,
        address indexed proposer,
        address indexed to,
        uint256 value,
        string description
    );
    event Approved(address indexed admin, uint256 indexed txId);
    event Executed(uint256 indexed txId);
    event StrategyProposed(
        uint256 indexed txId,
        StrategyType strategyType,
        address indexed protocol,
        address tokenIn,
        uint256 amountIn
    );
    event StrategyExecuted(
        uint256 indexed txId,
        StrategyType strategyType,
        address indexed protocol
    );
    event ProtocolApproved(address indexed protocol, string name);
    event ProtocolRevoked(address indexed protocol);
    event AdminAdded(address indexed admin);
    event ThresholdChanged(uint256 oldThreshold, uint256 newThreshold);

    // -------------------------------------------------------------------------
    // Structs
    // -------------------------------------------------------------------------

    struct Proposal {
        address to;
        uint256 value;
        bytes data;
        string description;
        bool executed;
        uint256 approvalCount;
        ProposalType proposalType;
        StrategyType strategyType;
        address tokenIn; // ERC20 token used as input; address(0) = ETH
        uint256 amountIn; // amount of tokenIn (for approve-before-call)
    }

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    address[] public admins;
    mapping(address => bool) public isAdmin;
    uint256 public threshold;

    Proposal[] public proposals;
    mapping(uint256 => mapping(address => bool)) public hasApproved;

    // Protocol whitelist
    mapping(address => bool) public approvedProtocols;
    address[] public approvedProtocolList;

    // Chainlink price feeds (optional – address(0) disables)
    AggregatorV3Interface public ethUsdFeed;
    AggregatorV3Interface public btcUsdFeed;

    /// @notice Maximum age of a price answer before it is considered stale
    uint256 public priceStaleThreshold = 3600; // 1 hour

    // -------------------------------------------------------------------------
    // Modifiers
    // -------------------------------------------------------------------------

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
        require(!hasApproved[_txId][msg.sender], "Already approved by you");
        _;
    }

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    /**
     * @param _admins       Initial admin addresses
     * @param _threshold    Required approval count
     * @param _ethUsdFeed   Chainlink ETH/USD feed (address(0) to disable)
     * @param _btcUsdFeed   Chainlink BTC/USD feed (address(0) to disable)
     */
    constructor(
        address[] memory _admins,
        uint256 _threshold,
        address _ethUsdFeed,
        address _btcUsdFeed
    ) {
        require(_admins.length > 0, "At least one admin required");
        require(
            _threshold > 0 && _threshold <= _admins.length,
            "Invalid threshold"
        );

        for (uint256 i = 0; i < _admins.length; i++) {
            address admin = _admins[i];
            require(admin != address(0), "Invalid admin address");
            require(!isAdmin[admin], "Duplicate admin");
            isAdmin[admin] = true;
            admins.push(admin);
            emit AdminAdded(admin);
        }

        threshold = _threshold;

        if (_ethUsdFeed != address(0))
            ethUsdFeed = AggregatorV3Interface(_ethUsdFeed);
        if (_btcUsdFeed != address(0))
            btcUsdFeed = AggregatorV3Interface(_btcUsdFeed);
    }

    // -------------------------------------------------------------------------
    // Receive ETH
    // -------------------------------------------------------------------------

    receive() external payable {
        emit Deposit(msg.sender, msg.value, address(this).balance);
    }

    fallback() external payable {
        emit Deposit(msg.sender, msg.value, address(this).balance);
    }

    // -------------------------------------------------------------------------
    // Protocol Whitelist Management (single-admin action – lower-risk governance)
    // -------------------------------------------------------------------------

    /**
     * @notice Add a protocol to the execution whitelist
     * @param _protocol Contract address of the protocol
     * @param _name     Human-readable name (e.g. "Uniswap V3 Router")
     */
    function approveProtocol(
        address _protocol,
        string calldata _name
    ) external onlyAdmin {
        require(_protocol != address(0), "Invalid protocol address");
        require(!approvedProtocols[_protocol], "Already approved");
        approvedProtocols[_protocol] = true;
        approvedProtocolList.push(_protocol);
        emit ProtocolApproved(_protocol, _name);
    }

    /**
     * @notice Remove a protocol from the whitelist
     */
    function revokeProtocol(address _protocol) external onlyAdmin {
        require(approvedProtocols[_protocol], "Protocol not approved");
        approvedProtocols[_protocol] = false;
        // Remove from list (order not preserved)
        for (uint256 i = 0; i < approvedProtocolList.length; i++) {
            if (approvedProtocolList[i] == _protocol) {
                approvedProtocolList[i] = approvedProtocolList[
                    approvedProtocolList.length - 1
                ];
                approvedProtocolList.pop();
                break;
            }
        }
        emit ProtocolRevoked(_protocol);
    }

    function getApprovedProtocols() external view returns (address[] memory) {
        return approvedProtocolList;
    }

    // -------------------------------------------------------------------------
    // Standard Transfer Proposal
    // -------------------------------------------------------------------------

    /**
     * @notice Create a proposal to transfer ETH or call an arbitrary contract
     */
    function propose(
        address _to,
        uint256 _value,
        bytes calldata _data,
        string calldata _description
    ) external onlyAdmin returns (uint256) {
        require(_to != address(0), "Invalid recipient");

        uint256 txId = proposals.length;
        proposals.push(
            Proposal({
                to: _to,
                value: _value,
                data: _data,
                description: _description,
                executed: false,
                approvalCount: 0,
                proposalType: ProposalType.TRANSFER,
                strategyType: StrategyType.NONE,
                tokenIn: address(0),
                amountIn: 0
            })
        );

        emit ProposalCreated(txId, msg.sender, _to, _value, _description);
        return txId;
    }

    // -------------------------------------------------------------------------
    // Strategy Proposal (generated by Python backend)
    // -------------------------------------------------------------------------

    /**
     * @notice Create an investment strategy proposal.
     *         The calldata and protocol address are generated by the backend.
     * @param _protocol      Whitelisted protocol to call
     * @param _ethValue      ETH to forward (0 for ERC20 strategies)
     * @param _calldata      ABI-encoded function call to execute on _protocol
     * @param _description   Human-readable strategy description
     * @param _strategyType  LENDING or ARBITRAGE
     * @param _tokenIn       ERC20 token to approve before calling (address(0) if none)
     * @param _amountIn      Amount of _tokenIn to approve
     */
    function proposeStrategy(
        address _protocol,
        uint256 _ethValue,
        bytes calldata _calldata,
        string calldata _description,
        StrategyType _strategyType,
        address _tokenIn,
        uint256 _amountIn
    ) external onlyAdmin returns (uint256) {
        require(_protocol != address(0), "Invalid protocol");
        require(
            _strategyType != StrategyType.NONE,
            "Must specify strategy type"
        );
        require(approvedProtocols[_protocol], "Protocol not in whitelist");

        uint256 txId = proposals.length;
        proposals.push(
            Proposal({
                to: _protocol,
                value: _ethValue,
                data: _calldata,
                description: _description,
                executed: false,
                approvalCount: 0,
                proposalType: ProposalType.STRATEGY,
                strategyType: _strategyType,
                tokenIn: _tokenIn,
                amountIn: _amountIn
            })
        );

        emit ProposalCreated(
            txId,
            msg.sender,
            _protocol,
            _ethValue,
            _description
        );
        emit StrategyProposed(
            txId,
            _strategyType,
            _protocol,
            _tokenIn,
            _amountIn
        );
        return txId;
    }

    // -------------------------------------------------------------------------
    // Approve & Execute
    // -------------------------------------------------------------------------

    function approve(
        uint256 _txId
    ) external onlyAdmin txExists(_txId) notExecuted(_txId) notApproved(_txId) {
        hasApproved[_txId][msg.sender] = true;
        proposals[_txId].approvalCount++;
        emit Approved(msg.sender, _txId);
    }

    function execute(
        uint256 _txId
    ) external onlyAdmin txExists(_txId) notExecuted(_txId) {
        Proposal storage proposal = proposals[_txId];

        // Count caller's approval if not yet given
        if (!hasApproved[_txId][msg.sender]) {
            hasApproved[_txId][msg.sender] = true;
            proposal.approvalCount++;
            emit Approved(msg.sender, _txId);
        }

        require(proposal.approvalCount >= threshold, "Not enough approvals");

        proposal.executed = true;

        if (proposal.proposalType == ProposalType.STRATEGY) {
            _executeStrategy(_txId, proposal);
        } else {
            _executeTransfer(proposal);
        }

        emit Executed(_txId);
    }

    // -------------------------------------------------------------------------
    // Internal Execution
    // -------------------------------------------------------------------------

    function _executeTransfer(Proposal storage proposal) internal {
        (bool success, ) = proposal.to.call{value: proposal.value}(
            proposal.data
        );
        require(success, "Transfer execution failed");
    }

    function _executeStrategy(
        uint256 _txId,
        Proposal storage proposal
    ) internal {
        require(approvedProtocols[proposal.to], "Protocol not approved");

        // Approve ERC20 allowance if needed (safe approve pattern)
        if (proposal.tokenIn != address(0) && proposal.amountIn > 0) {
            // Reset allowance to 0 first (required by some tokens like USDC)
            IERC20(proposal.tokenIn).approve(proposal.to, 0);
            // Then set the desired allowance and verify success
            bool approved = IERC20(proposal.tokenIn).approve(
                proposal.to,
                proposal.amountIn
            );
            require(approved, "ERC20 approve failed");
        }

        (bool success, bytes memory returnData) = proposal.to.call{
            value: proposal.value
        }(proposal.data);

        if (!success) {
            // Bubble up revert reason
            if (returnData.length > 0) {
                assembly {
                    revert(add(32, returnData), mload(returnData))
                }
            }
            revert("Strategy execution failed");
        }

        emit StrategyExecuted(_txId, proposal.strategyType, proposal.to);
    }

    // -------------------------------------------------------------------------
    // Chainlink Price Feeds
    // -------------------------------------------------------------------------

    /**
     * @notice Read the latest ETH/USD price from Chainlink
     * @return price      Price with feed decimals (usually 8)
     * @return updatedAt  Timestamp of the last update
     */
    function getEthUsdPrice()
        external
        view
        returns (int256 price, uint256 updatedAt)
    {
        require(
            address(ethUsdFeed) != address(0),
            "ETH/USD feed not configured"
        );
        (, price, , updatedAt, ) = ethUsdFeed.latestRoundData();
    }

    /**
     * @notice Read the latest BTC/USD price from Chainlink
     */
    function getBtcUsdPrice()
        external
        view
        returns (int256 price, uint256 updatedAt)
    {
        require(
            address(btcUsdFeed) != address(0),
            "BTC/USD feed not configured"
        );
        (, price, , updatedAt, ) = btcUsdFeed.latestRoundData();
    }

    /**
     * @notice Returns true if updatedAt is within priceStaleThreshold
     */
    function isPriceFresh(uint256 updatedAt) public view returns (bool) {
        return (block.timestamp - updatedAt) <= priceStaleThreshold;
    }

    // -------------------------------------------------------------------------
    // View Helpers
    // -------------------------------------------------------------------------

    function getAdminCount() external view returns (uint256) {
        return admins.length;
    }
    function getAdmins() external view returns (address[] memory) {
        return admins;
    }
    function getProposalCount() external view returns (uint256) {
        return proposals.length;
    }

    function getProposal(
        uint256 _txId
    )
        external
        view
        returns (
            address to,
            uint256 value,
            bytes memory data,
            string memory description,
            bool executed,
            uint256 approvalCount,
            ProposalType proposalType,
            StrategyType strategyType,
            address tokenIn,
            uint256 amountIn
        )
    {
        Proposal storage p = proposals[_txId];
        return (
            p.to,
            p.value,
            p.data,
            p.description,
            p.executed,
            p.approvalCount,
            p.proposalType,
            p.strategyType,
            p.tokenIn,
            p.amountIn
        );
    }

    function canExecute(uint256 _txId) external view returns (bool) {
        if (_txId >= proposals.length) return false;
        Proposal storage p = proposals[_txId];
        return !p.executed && p.approvalCount >= threshold;
    }

    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }

    function getTokenBalance(address token) external view returns (uint256) {
        return IERC20(token).balanceOf(address(this));
    }
}
