// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/MultisigWallet.sol";

contract MultisigWalletTest is Test {
    MultisigWallet public wallet;

    address public admin1;
    address public admin2;
    address public admin3;
    address public nonAdmin;
    address public recipient;

    uint256 public constant INITIAL_BALANCE = 10 ether;
    uint256 public constant THRESHOLD = 2;

    event Deposit(address indexed sender, uint256 amount, uint256 balance);
    event ProposalCreated(uint256 indexed txId, address indexed proposer, address indexed to, uint256 value, bytes data, string description);
    event Approved(address indexed admin, uint256 indexed txId);
    event Executed(uint256 indexed txId);

    function setUp() public {
        // Setup accounts
        admin1 = makeAddr("admin1");
        admin2 = makeAddr("admin2");
        admin3 = makeAddr("admin3");
        nonAdmin = makeAddr("nonAdmin");
        recipient = makeAddr("recipient");

        // Create admins array
        address[] memory admins = new address[](3);
        admins[0] = admin1;
        admins[1] = admin2;
        admins[2] = admin3;

        // Deploy wallet
        wallet = new MultisigWallet(admins, THRESHOLD);

        // Fund the wallet
        vm.deal(address(wallet), INITIAL_BALANCE);
    }

    // ========== CONSTRUCTOR TESTS ==========

    function test_Constructor() public view {
        assertEq(wallet.getAdminCount(), 3);
        assertEq(wallet.threshold(), THRESHOLD);
        assertTrue(wallet.isAdmin(admin1));
        assertTrue(wallet.isAdmin(admin2));
        assertTrue(wallet.isAdmin(admin3));
        assertFalse(wallet.isAdmin(nonAdmin));
    }

    function test_Constructor_RevertOnEmptyAdmins() public {
        address[] memory emptyAdmins = new address[](0);
        vm.expectRevert("At least one admin required");
        new MultisigWallet(emptyAdmins, 1);
    }

    function test_Constructor_RevertOnZeroThreshold() public {
        address[] memory admins = new address[](1);
        admins[0] = admin1;
        vm.expectRevert("Invalid threshold");
        new MultisigWallet(admins, 0);
    }

    function test_Constructor_RevertOnThresholdTooHigh() public {
        address[] memory admins = new address[](2);
        admins[0] = admin1;
        admins[1] = admin2;
        vm.expectRevert("Invalid threshold");
        new MultisigWallet(admins, 3);
    }

    function test_Constructor_RevertOnDuplicateAdmin() public {
        address[] memory admins = new address[](2);
        admins[0] = admin1;
        admins[1] = admin1;
        vm.expectRevert("Duplicate admin");
        new MultisigWallet(admins, 1);
    }

    // ========== DEPOSIT TESTS ==========

    function test_ReceiveEther() public {
        uint256 amount = 1 ether;
        uint256 balanceBefore = address(wallet).balance;

        vm.deal(nonAdmin, amount);
        vm.prank(nonAdmin);
        (bool success, ) = address(wallet).call{value: amount}("");
        assertTrue(success);

        assertEq(address(wallet).balance, balanceBefore + amount);
    }

    function test_ReceiveEther_EmitsEvent() public {
        uint256 amount = 1 ether;
        vm.deal(nonAdmin, amount);

        vm.expectEmit(true, false, false, true);
        emit Deposit(nonAdmin, amount, INITIAL_BALANCE + amount);

        vm.prank(nonAdmin);
        (bool success, ) = address(wallet).call{value: amount}("");
        assertTrue(success);
    }

    // ========== PROPOSE TESTS ==========

    function test_Propose() public {
        uint256 value = 1 ether;
        string memory description = "Test proposal";

        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, value, "", description);

        assertEq(txId, 0);
        assertEq(wallet.getProposalCount(), 1);

        (address to, uint256 propValue, , string memory desc, bool executed, uint256 approvalCount) = wallet.getProposal(0);
        assertEq(to, recipient);
        assertEq(propValue, value);
        assertEq(desc, description);
        assertFalse(executed);
        assertEq(approvalCount, 0);
    }

    function test_Propose_RevertOnNonAdmin() public {
        vm.prank(nonAdmin);
        vm.expectRevert("Not an admin");
        wallet.propose(recipient, 1 ether, "", "Test");
    }

    function test_Propose_RevertOnZeroAddress() public {
        vm.prank(admin1);
        vm.expectRevert("Invalid recipient");
        wallet.propose(address(0), 1 ether, "", "Test");
    }

    // ========== APPROVE TESTS ==========

    function test_Approve() public {
        // Create proposal
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, 1 ether, "", "Test");

        // Approve
        vm.prank(admin2);
        wallet.approve(txId);

        assertTrue(wallet.hasApproved(txId, admin2));
        (, , , , , uint256 approvalCount) = wallet.getProposal(txId);
        assertEq(approvalCount, 1);
    }

    function test_Approve_RevertOnNonAdmin() public {
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, 1 ether, "", "Test");

        vm.prank(nonAdmin);
        vm.expectRevert("Not an admin");
        wallet.approve(txId);
    }

    function test_Approve_RevertOnNonExistentTx() public {
        vm.prank(admin1);
        vm.expectRevert("Transaction does not exist");
        wallet.approve(999);
    }

    function test_Approve_RevertOnDoubleApproval() public {
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, 1 ether, "", "Test");

        vm.prank(admin2);
        wallet.approve(txId);

        vm.prank(admin2);
        vm.expectRevert("Transaction already approved by you");
        wallet.approve(txId);
    }

    // ========== EXECUTE TESTS ==========

    function test_Execute() public {
        uint256 amount = 1 ether;
        uint256 recipientBalanceBefore = recipient.balance;

        // Create and approve proposal
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, amount, "", "Test");

        vm.prank(admin2);
        wallet.approve(txId);

        // Execute
        vm.prank(admin3);
        wallet.execute(txId);

        (, , , , bool executed, ) = wallet.getProposal(txId);
        assertTrue(executed);
        assertEq(recipient.balance, recipientBalanceBefore + amount);
    }

    function test_Execute_CountsAsApproval() public {
        uint256 amount = 1 ether;

        // Create proposal
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, amount, "", "Test");

        // First approve
        vm.prank(admin2);
        wallet.approve(txId);

        // Execute by admin3 (should count as second approval and execute)
        vm.prank(admin3);
        wallet.execute(txId);

        (, , , , bool executed, uint256 approvalCount) = wallet.getProposal(txId);
        assertTrue(executed);
        assertEq(approvalCount, 2);
    }

    function test_Execute_RevertOnInsufficientApprovals() public {
        // Create proposal (no approvals yet)
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, 1 ether, "", "Test");

        // Try to execute without enough approvals (only 1 from execute call)
        vm.prank(admin2);
        vm.expectRevert("Not enough approvals");
        wallet.execute(txId);
    }

    function test_Execute_RevertOnAlreadyExecuted() public {
        uint256 amount = 1 ether;

        // Create, approve, and execute proposal
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, amount, "", "Test");

        vm.prank(admin2);
        wallet.approve(txId);

        vm.prank(admin3);
        wallet.execute(txId);

        // Try to execute again
        vm.prank(admin1);
        vm.expectRevert("Transaction already executed");
        wallet.execute(txId);
    }

    // ========== VIEW FUNCTION TESTS ==========

    function test_CanExecute() public {
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, 1 ether, "", "Test");

        // Not enough approvals yet
        assertFalse(wallet.canExecute(txId));

        // Add approvals
        vm.prank(admin2);
        wallet.approve(txId);

        vm.prank(admin3);
        wallet.approve(txId);

        // Now can execute
        assertTrue(wallet.canExecute(txId));
    }

    function test_GetBalance() public view {
        assertEq(wallet.getBalance(), INITIAL_BALANCE);
    }

    function test_GetAdmins() public view {
        address[] memory admins = wallet.getAdmins();
        assertEq(admins.length, 3);
        assertEq(admins[0], admin1);
        assertEq(admins[1], admin2);
        assertEq(admins[2], admin3);
    }

    // ========== INTEGRATION TESTS ==========

    function test_FullWorkflow() public {
        uint256 amount = 2 ether;
        uint256 recipientBalanceBefore = recipient.balance;

        // Admin1 proposes
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, amount, "", "Pay vendor");

        // Admin2 approves
        vm.prank(admin2);
        wallet.approve(txId);

        // Admin1 executes (counts as approval too, making it 2/3)
        vm.prank(admin1);
        wallet.execute(txId);

        // Verify
        assertEq(recipient.balance, recipientBalanceBefore + amount);
        assertEq(address(wallet).balance, INITIAL_BALANCE - amount);
    }

    function test_MultipleProposals() public {
        // Create multiple proposals
        vm.startPrank(admin1);
        uint256 txId1 = wallet.propose(recipient, 1 ether, "", "Proposal 1");
        uint256 txId2 = wallet.propose(recipient, 2 ether, "", "Proposal 2");
        vm.stopPrank();

        assertEq(wallet.getProposalCount(), 2);
        assertEq(txId1, 0);
        assertEq(txId2, 1);

        // Execute first proposal
        vm.prank(admin2);
        wallet.approve(txId1);
        vm.prank(admin3);
        wallet.execute(txId1);

        // First should be executed, second should not
        (, , , , bool executed1, ) = wallet.getProposal(txId1);
        (, , , , bool executed2, ) = wallet.getProposal(txId2);
        assertTrue(executed1);
        assertFalse(executed2);
    }
}
