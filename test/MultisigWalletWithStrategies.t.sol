// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/MultisigWalletWithStrategies.sol";

// ---------------------------------------------------------------------------
// Mock Chainlink feed
// ---------------------------------------------------------------------------
contract MockV3Aggregator {
    int256 public price;
    uint256 public updatedAt;
    uint8 public constant decimals = 8;

    constructor(int256 _price) {
        price = _price;
        updatedAt = block.timestamp;
    }

    function setPrice(int256 _price) external {
        price = _price;
        updatedAt = block.timestamp;
    }

    function setUpdatedAt(uint256 _ts) external {
        updatedAt = _ts;
    }

    function latestRoundData() external view returns (
        uint80, int256, uint256, uint256, uint80
    ) {
        return (1, price, block.timestamp, updatedAt, 1);
    }
}

// ---------------------------------------------------------------------------
// Mock protocol (records calls via a real function that sets state)
// ---------------------------------------------------------------------------
contract MockProtocol {
    bool public wasCalled;
    bool public shouldRevert;

    function setShouldRevert(bool _r) external { shouldRevert = _r; }

    // Called when abi.encodeWithSignature("doWork(uint256)", ...) is used
    function doWork(uint256) external {
        if (shouldRevert) revert("MockProtocol: forced revert");
        wasCalled = true;
    }

    fallback() external payable {
        if (shouldRevert) revert("MockProtocol: forced revert");
        wasCalled = true;
    }

    receive() external payable {
        if (shouldRevert) revert("MockProtocol: forced revert");
        wasCalled = true;
    }
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------
contract MultisigWalletWithStrategiesTest is Test {
    MultisigWalletWithStrategies wallet;
    MockV3Aggregator ethFeed;
    MockV3Aggregator btcFeed;
    MockProtocol mockProtocol;

    address alice = address(0xA11CE);
    address bob   = address(0xB0B);
    address carol = address(0xCA401);
    address eve   = address(0xEEE);

    function setUp() public {
        ethFeed = new MockV3Aggregator(2000e8);  // $2000 / ETH
        btcFeed = new MockV3Aggregator(40000e8); // $40000 / BTC
        mockProtocol = new MockProtocol();

        address[] memory admins = new address[](3);
        admins[0] = alice;
        admins[1] = bob;
        admins[2] = carol;

        wallet = new MultisigWalletWithStrategies(
            admins,
            2,
            address(ethFeed),
            address(btcFeed)
        );

        // Fund wallet
        vm.deal(address(wallet), 10 ether);
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    function test_constructor_admins() public view {
        assertEq(wallet.getAdminCount(), 3);
        assertTrue(wallet.isAdmin(alice));
        assertTrue(wallet.isAdmin(bob));
        assertTrue(wallet.isAdmin(carol));
        assertFalse(wallet.isAdmin(eve));
    }

    function test_constructor_threshold() public view {
        assertEq(wallet.threshold(), 2);
    }

    function test_constructor_feeds() public view {
        assertEq(address(wallet.ethUsdFeed()), address(ethFeed));
        assertEq(address(wallet.btcUsdFeed()), address(btcFeed));
    }

    function test_constructor_invalid_threshold() public {
        address[] memory admins = new address[](2);
        admins[0] = alice;
        admins[1] = bob;
        vm.expectRevert("Invalid threshold");
        new MultisigWalletWithStrategies(admins, 3, address(0), address(0));
    }

    // -----------------------------------------------------------------------
    // Protocol Whitelist
    // -----------------------------------------------------------------------

    function test_approveProtocol() public {
        vm.prank(alice);
        wallet.approveProtocol(address(mockProtocol), "MockProtocol");
        assertTrue(wallet.approvedProtocols(address(mockProtocol)));

        address[] memory list = wallet.getApprovedProtocols();
        assertEq(list.length, 1);
        assertEq(list[0], address(mockProtocol));
    }

    function test_revokeProtocol() public {
        vm.prank(alice);
        wallet.approveProtocol(address(mockProtocol), "MockProtocol");

        vm.prank(bob);
        wallet.revokeProtocol(address(mockProtocol));

        assertFalse(wallet.approvedProtocols(address(mockProtocol)));
        assertEq(wallet.getApprovedProtocols().length, 0);
    }

    function test_approveProtocol_nonAdmin_reverts() public {
        vm.prank(eve);
        vm.expectRevert("Not an admin");
        wallet.approveProtocol(address(mockProtocol), "X");
    }

    function test_approveProtocol_duplicate_reverts() public {
        vm.prank(alice);
        wallet.approveProtocol(address(mockProtocol), "X");
        vm.prank(alice);
        vm.expectRevert("Already approved");
        wallet.approveProtocol(address(mockProtocol), "X");
    }

    // -----------------------------------------------------------------------
    // Transfer Proposal
    // -----------------------------------------------------------------------

    function test_proposeTransfer() public {
        vm.prank(alice);
        uint256 txId = wallet.propose(bob, 1 ether, "", "Pay Bob");
        assertEq(txId, 0);
        assertEq(wallet.getProposalCount(), 1);
    }

    function test_proposeTransfer_nonAdmin_reverts() public {
        vm.prank(eve);
        vm.expectRevert("Not an admin");
        wallet.propose(bob, 0, "", "x");
    }

    function test_approveAndExecuteTransfer() public {
        uint256 beforeBal = bob.balance;

        vm.prank(alice);
        wallet.propose(bob, 1 ether, "", "Pay Bob");

        vm.prank(alice);
        wallet.approve(0);

        vm.prank(bob);
        wallet.execute(0);  // bob's execute counts as approval → 2/2

        assertEq(bob.balance, beforeBal + 1 ether);

        (,,,, bool executed,,,,, ) = wallet.getProposal(0);
        assertTrue(executed);
    }

    // -----------------------------------------------------------------------
    // Strategy Proposal
    // -----------------------------------------------------------------------

    function test_proposeStrategy_notWhitelisted_reverts() public {
        vm.prank(alice);
        vm.expectRevert("Protocol not in whitelist");
        wallet.proposeStrategy(
            address(mockProtocol),
            0,
            abi.encodeWithSignature("doWork(uint256)", 100),
            "Test strategy",
            MultisigWalletWithStrategies.StrategyType.LENDING,
            address(0),
            0
        );
    }

    function test_proposeStrategy_success() public {
        vm.prank(alice);
        wallet.approveProtocol(address(mockProtocol), "Mock");

        vm.prank(alice);
        uint256 txId = wallet.proposeStrategy(
            address(mockProtocol),
            0,
            abi.encodeWithSignature("doWork(uint256)", 42),
            "Lend to Mock",
            MultisigWalletWithStrategies.StrategyType.LENDING,
            address(0),
            0
        );

        assertEq(txId, 0);

        (address to,,,, bool executed,, MultisigWalletWithStrategies.ProposalType pType,
         MultisigWalletWithStrategies.StrategyType sType,,) = wallet.getProposal(0);

        assertEq(to, address(mockProtocol));
        assertFalse(executed);
        assertEq(uint8(pType), uint8(MultisigWalletWithStrategies.ProposalType.STRATEGY));
        assertEq(uint8(sType), uint8(MultisigWalletWithStrategies.StrategyType.LENDING));
    }

    function test_executeStrategy_success() public {
        vm.prank(alice);
        wallet.approveProtocol(address(mockProtocol), "Mock");

        vm.prank(alice);
        // Use doWork(uint256) — a real function that sets wasCalled = true
        wallet.proposeStrategy(
            address(mockProtocol),
            0,
            abi.encodeWithSignature("doWork(uint256)", 42),
            "Lend to Mock",
            MultisigWalletWithStrategies.StrategyType.LENDING,
            address(0),
            0
        );

        vm.prank(alice);
        wallet.approve(0);

        vm.prank(bob);
        wallet.execute(0);

        assertTrue(mockProtocol.wasCalled());
    }

    function test_executeStrategy_notWhitelisted_reverts() public {
        // Whitelist, propose, then revoke before execution
        vm.prank(alice);
        wallet.approveProtocol(address(mockProtocol), "Mock");

        vm.prank(alice);
        wallet.proposeStrategy(
            address(mockProtocol),
            0,
            abi.encodeWithSignature("doWork(uint256)", 1),
            "Test",
            MultisigWalletWithStrategies.StrategyType.ARBITRAGE,
            address(0),
            0
        );

        // Revoke before execution
        vm.prank(bob);
        wallet.revokeProtocol(address(mockProtocol));

        vm.prank(alice);
        wallet.approve(0);

        vm.prank(bob);
        vm.expectRevert("Protocol not approved");
        wallet.execute(0);
    }

    function test_executeStrategy_protocolReverts() public {
        // setShouldRevert must be called before the protocol is whitelisted,
        // so the mock state is set correctly
        mockProtocol.setShouldRevert(true);

        vm.prank(alice);
        wallet.approveProtocol(address(mockProtocol), "Mock");

        vm.prank(alice);
        // Use doWork – the function checks shouldRevert and reverts
        wallet.proposeStrategy(
            address(mockProtocol),
            0,
            abi.encodeWithSignature("doWork(uint256)", 0),
            "Should fail",
            MultisigWalletWithStrategies.StrategyType.LENDING,
            address(0),
            0
        );

        vm.prank(alice);
        wallet.approve(0);

        vm.prank(bob);
        vm.expectRevert("MockProtocol: forced revert");
        wallet.execute(0);
    }

    // -----------------------------------------------------------------------
    // Chainlink Prices
    // -----------------------------------------------------------------------

    function test_getEthUsdPrice() public view {
        (int256 price, uint256 updatedAt) = wallet.getEthUsdPrice();
        assertEq(price, 2000e8);
        assertTrue(updatedAt > 0);
    }

    function test_getBtcUsdPrice() public view {
        (int256 price,) = wallet.getBtcUsdPrice();
        assertEq(price, 40000e8);
    }

    function test_isPriceFresh_fresh() public {
        // Warp to a realistic timestamp so subtraction doesn't underflow
        vm.warp(10_000);
        assertTrue(wallet.isPriceFresh(block.timestamp - 100));
    }

    function test_isPriceFresh_stale() public {
        vm.warp(10_000);
        assertFalse(wallet.isPriceFresh(block.timestamp - 7200));
    }

    function test_ethFeedNotConfigured_reverts() public {
        address[] memory admins = new address[](1);
        admins[0] = alice;
        MultisigWalletWithStrategies w2 = new MultisigWalletWithStrategies(
            admins, 1, address(0), address(0)
        );
        vm.expectRevert("ETH/USD feed not configured");
        w2.getEthUsdPrice();
    }

    // -----------------------------------------------------------------------
    // Access control edge cases
    // -----------------------------------------------------------------------

    function test_cannotApproveTwice() public {
        vm.prank(alice);
        wallet.propose(bob, 0, "", "x");

        vm.prank(alice);
        wallet.approve(0);

        vm.prank(alice);
        vm.expectRevert("Already approved by you");
        wallet.approve(0);
    }

    function test_cannotExecuteTwice() public {
        vm.prank(alice);
        wallet.propose(bob, 0, "", "x");

        vm.prank(alice);
        wallet.approve(0);

        vm.prank(bob);
        wallet.execute(0);

        vm.prank(carol);
        vm.expectRevert("Transaction already executed");
        wallet.execute(0);
    }

    function test_cannotExecuteWithoutEnoughApprovals() public {
        vm.prank(alice);
        wallet.propose(bob, 1 ether, "", "x");

        // Only alice approves (1 < threshold=2), execute should fail
        vm.prank(alice);
        vm.expectRevert("Not enough approvals");
        wallet.execute(0);
    }

    // -----------------------------------------------------------------------
    // canExecute view
    // -----------------------------------------------------------------------

    function test_canExecute() public {
        vm.prank(alice);
        wallet.propose(bob, 0, "", "x");

        assertFalse(wallet.canExecute(0));

        vm.prank(alice);
        wallet.approve(0);
        assertFalse(wallet.canExecute(0));

        vm.prank(bob);
        wallet.approve(0);
        assertTrue(wallet.canExecute(0));
    }

    // -----------------------------------------------------------------------
    // Receive ETH
    // -----------------------------------------------------------------------

    function test_receiveEth() public {
        uint256 before = address(wallet).balance;
        (bool ok,) = address(wallet).call{value: 1 ether}("");
        assertTrue(ok);
        assertEq(address(wallet).balance, before + 1 ether);
    }
}
