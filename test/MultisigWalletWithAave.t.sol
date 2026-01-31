// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/MultisigWalletWithAave.sol";

contract MultisigWalletWithAaveTest is Test {
    MultisigWalletWithAave public wallet;

    address public admin1;
    address public admin2;
    address public admin3;
    address public nonAdmin;
    address public recipient;

    uint256 public constant INITIAL_BALANCE = 10 ether;
    uint256 public constant THRESHOLD = 2;

    function setUp() public {
        admin1 = makeAddr("admin1");
        admin2 = makeAddr("admin2");
        admin3 = makeAddr("admin3");
        nonAdmin = makeAddr("nonAdmin");
        recipient = makeAddr("recipient");

        address[] memory admins = new address[](3);
        admins[0] = admin1;
        admins[1] = admin2;
        admins[2] = admin3;

        // Deploy without Aave (pass address(0) for aavePool)
        wallet = new MultisigWalletWithAave(admins, THRESHOLD, address(0), address(0));

        vm.deal(address(wallet), INITIAL_BALANCE);
    }

    function test_Constructor() public view {
        assertEq(wallet.getAdminCount(), 3);
        assertEq(wallet.threshold(), THRESHOLD);
        assertTrue(wallet.isAdmin(admin1));
        assertTrue(wallet.isAdmin(admin2));
        assertTrue(wallet.isAdmin(admin3));
        assertFalse(wallet.aaveEnabled());
    }

    function test_ProposeTransfer() public {
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, 1 ether, "", "Test transfer");

        (address to, uint256 value, , string memory desc, bool executed, uint256 approvalCount, , ) = wallet.getProposal(txId);

        assertEq(to, recipient);
        assertEq(value, 1 ether);
        assertEq(desc, "Test transfer");
        assertFalse(executed);
        assertEq(approvalCount, 0);
    }

    function test_ApproveAndExecute() public {
        uint256 amount = 1 ether;
        uint256 recipientBalanceBefore = recipient.balance;

        // Create proposal
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, amount, "", "Test");

        // Approve
        vm.prank(admin2);
        wallet.approve(txId);

        // Execute (counts as approval too)
        vm.prank(admin3);
        wallet.execute(txId);

        (, , , , bool executed, uint256 approvalCount, , ) = wallet.getProposal(txId);
        assertTrue(executed);
        assertEq(approvalCount, 2);
        assertEq(recipient.balance, recipientBalanceBefore + amount);
    }

    function test_ProposeAaveDeposit_RevertWhenDisabled() public {
        vm.prank(admin1);
        vm.expectRevert("Aave not enabled");
        wallet.proposeAaveDeposit(address(0), 1 ether, "Deposit to Aave");
    }

    function test_ProposeAaveWithdraw_RevertWhenDisabled() public {
        vm.prank(admin1);
        vm.expectRevert("Aave not enabled");
        wallet.proposeAaveWithdraw(address(0), 1 ether, "Withdraw from Aave");
    }

    function test_MultipleProposalsWorkflow() public {
        // Admin1 creates two proposals
        vm.startPrank(admin1);
        uint256 txId1 = wallet.propose(recipient, 1 ether, "", "Proposal 1");
        uint256 txId2 = wallet.propose(recipient, 2 ether, "", "Proposal 2");
        vm.stopPrank();

        assertEq(wallet.getProposalCount(), 2);

        // Admin2 approves both
        vm.startPrank(admin2);
        wallet.approve(txId1);
        wallet.approve(txId2);
        vm.stopPrank();

        // Admin3 executes first one
        vm.prank(admin3);
        wallet.execute(txId1);

        // Check states
        (, , , , bool executed1, , , ) = wallet.getProposal(txId1);
        (, , , , bool executed2, , , ) = wallet.getProposal(txId2);

        assertTrue(executed1);
        assertFalse(executed2);
        assertTrue(wallet.canExecute(txId2));
    }

    function test_GetBalance() public view {
        assertEq(wallet.getBalance(), INITIAL_BALANCE);
    }

    function test_ReceiveETH() public {
        uint256 amount = 5 ether;
        vm.deal(nonAdmin, amount);

        vm.prank(nonAdmin);
        (bool success, ) = address(wallet).call{value: amount}("");

        assertTrue(success);
        assertEq(wallet.getBalance(), INITIAL_BALANCE + amount);
    }

    function test_OnlyAdminCanPropose() public {
        vm.prank(nonAdmin);
        vm.expectRevert("Not an admin");
        wallet.propose(recipient, 1 ether, "", "Test");
    }

    function test_OnlyAdminCanApprove() public {
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, 1 ether, "", "Test");

        vm.prank(nonAdmin);
        vm.expectRevert("Not an admin");
        wallet.approve(txId);
    }

    function test_OnlyAdminCanExecute() public {
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, 1 ether, "", "Test");

        vm.prank(admin2);
        wallet.approve(txId);

        vm.prank(nonAdmin);
        vm.expectRevert("Not an admin");
        wallet.execute(txId);
    }

    function test_CannotAproveTwice() public {
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, 1 ether, "", "Test");

        vm.prank(admin2);
        wallet.approve(txId);

        vm.prank(admin2);
        vm.expectRevert("Transaction already approved by you");
        wallet.approve(txId);
    }

    function test_CannotExecuteTwice() public {
        vm.prank(admin1);
        uint256 txId = wallet.propose(recipient, 1 ether, "", "Test");

        vm.prank(admin2);
        wallet.approve(txId);

        vm.prank(admin3);
        wallet.execute(txId);

        vm.prank(admin1);
        vm.expectRevert("Transaction already executed");
        wallet.execute(txId);
    }
}
