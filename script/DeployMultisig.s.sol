// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MultisigWallet.sol";

contract DeployMultisig is Script {
    function run() external {
        // Get private key from environment
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        // Get admin addresses from environment or use defaults
        address admin1 = vm.envOr("ADMIN1", vm.addr(deployerPrivateKey));
        address admin2 = vm.envOr("ADMIN2", address(0x70997970C51812dc3A010C7d01b50e0d17dc79C8));
        address admin3 = vm.envOr("ADMIN3", address(0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC));

        address[] memory admins = new address[](3);
        admins[0] = admin1;
        admins[1] = admin2;
        admins[2] = admin3;

        uint256 threshold = 2; // 2-of-3 multisig

        vm.startBroadcast(deployerPrivateKey);

        MultisigWallet wallet = new MultisigWallet(admins, threshold);

        console.log("MultisigWallet deployed at:", address(wallet));
        console.log("Admins:");
        console.log("  - Admin 1:", admin1);
        console.log("  - Admin 2:", admin2);
        console.log("  - Admin 3:", admin3);
        console.log("Threshold:", threshold);

        vm.stopBroadcast();
    }
}
