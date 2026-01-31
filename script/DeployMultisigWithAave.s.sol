// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MultisigWalletWithAave.sol";
import "../src/AaveAddresses.sol";

contract DeployMultisigWithAave is Script {
    function run() external {
        // Get private key from environment
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        // Get admin addresses
        address admin1 = vm.envOr("ADMIN1", vm.addr(deployerPrivateKey));
        address admin2 = vm.envOr("ADMIN2", address(0x70997970C51812dc3A010C7d01b50e0d17dc79C8));
        address admin3 = vm.envOr("ADMIN3", address(0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC));

        address[] memory admins = new address[](3);
        admins[0] = admin1;
        admins[1] = admin2;
        admins[2] = admin3;

        uint256 threshold = 2;

        // Determine network and get Aave addresses
        uint256 chainId = block.chainid;
        address aavePool;
        address weth;

        if (chainId == 1) {
            // Mainnet
            aavePool = AaveAddresses.MAINNET_POOL;
            weth = AaveAddresses.MAINNET_WETH;
        } else if (chainId == 11155111) {
            // Sepolia
            aavePool = AaveAddresses.SEPOLIA_POOL;
            weth = AaveAddresses.SEPOLIA_WETH;
        } else {
            // Local/other - disable Aave
            aavePool = address(0);
            weth = address(0);
        }

        vm.startBroadcast(deployerPrivateKey);

        MultisigWalletWithAave wallet = new MultisigWalletWithAave(
            admins,
            threshold,
            aavePool,
            weth
        );

        console.log("MultisigWalletWithAave deployed at:", address(wallet));
        console.log("Chain ID:", chainId);
        console.log("Aave Pool:", aavePool);
        console.log("WETH:", weth);
        console.log("Admins:");
        console.log("  - Admin 1:", admin1);
        console.log("  - Admin 2:", admin2);
        console.log("  - Admin 3:", admin3);

        vm.stopBroadcast();
    }
}
