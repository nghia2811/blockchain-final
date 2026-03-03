// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MultisigWalletWithStrategies.sol";

/**
 * @notice Deployment script for MultisigWalletWithStrategies.
 *
 * Network detection:
 *   chainId 1        → Ethereum Mainnet  (real Chainlink feeds)
 *   chainId 11155111 → Sepolia Testnet   (Sepolia Chainlink feeds)
 *   other            → Local/Anvil       (feeds disabled)
 *
 * After deployment, admins must call approveProtocol() for each
 * external protocol (Uniswap V3 Router, Compound V3, Aave V3, …).
 */
contract DeployMultisigWithStrategies is Script {
    // -------------------------------------------------------------------------
    // Chainlink Feed Addresses
    // -------------------------------------------------------------------------

    // Mainnet
    address constant MAINNET_ETH_USD = 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419;
    address constant MAINNET_BTC_USD = 0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c;

    // Sepolia
    address constant SEPOLIA_ETH_USD = 0x694AA1769357215DE4FAC081bf1f309aDC325306;
    address constant SEPOLIA_BTC_USD = 0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43;

    // -------------------------------------------------------------------------
    // Protocol Addresses (for post-deploy reference)
    // -------------------------------------------------------------------------

    // Uniswap V3 Router (same on mainnet and Sepolia)
    address constant UNISWAP_V3_ROUTER = 0xE592427A0AEce92De3Edee1F18E0157C05861564;
    // Compound V3 USDC Comet (mainnet)
    address constant COMPOUND_V3_USDC  = 0xc3d688B66703497DAA19211EEdff47f25384cdc3;
    // Aave V3 Pool (mainnet)
    address constant AAVE_V3_POOL      = 0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2;

    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        address deployer    = vm.addr(deployerKey);

        // Admin configuration – override via env vars ADMIN1/ADMIN2/ADMIN3
        address admin1 = vm.envOr("ADMIN1", deployer);
        address admin2 = vm.envOr("ADMIN2", address(0x70997970C51812dc3A010C7d01b50e0d17dc79C8));
        address admin3 = vm.envOr("ADMIN3", address(0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC));

        address[] memory admins = new address[](3);
        admins[0] = admin1;
        admins[1] = admin2;
        admins[2] = admin3;

        uint256 requiredThreshold = 2; // 2-of-3 multisig

        // Select Chainlink feeds based on network
        address ethUsdFeed;
        address btcUsdFeed;

        if (block.chainid == 1) {
            ethUsdFeed = MAINNET_ETH_USD;
            btcUsdFeed = MAINNET_BTC_USD;
            console.log("Network: Ethereum Mainnet");
        } else if (block.chainid == 11155111) {
            ethUsdFeed = SEPOLIA_ETH_USD;
            btcUsdFeed = SEPOLIA_BTC_USD;
            console.log("Network: Sepolia Testnet");
        } else {
            ethUsdFeed = address(0);
            btcUsdFeed = address(0);
            console.log("Network: Local/Anvil (Chainlink feeds disabled)");
        }

        vm.startBroadcast(deployerKey);

        MultisigWalletWithStrategies wallet = new MultisigWalletWithStrategies(
            admins,
            requiredThreshold,
            ethUsdFeed,
            btcUsdFeed
        );

        vm.stopBroadcast();

        // -------------------------------------------------------------------------
        // Log deployment details
        // -------------------------------------------------------------------------
        console.log("=== MultisigWalletWithStrategies deployed ===");
        console.log("Address     :", address(wallet));
        console.log("Admin 1     :", admin1);
        console.log("Admin 2     :", admin2);
        console.log("Admin 3     :", admin3);
        console.log("Threshold   :", requiredThreshold);
        console.log("ETH/USD Feed:", ethUsdFeed);
        console.log("BTC/USD Feed:", btcUsdFeed);
        console.log("");
        console.log("=== Next steps: whitelist protocols ===");
        console.log("cast send <CONTRACT> \"approveProtocol(address,string)\"", UNISWAP_V3_ROUTER, "\"Uniswap V3 Router\" --private-key $PRIVATE_KEY");
        console.log("cast send <CONTRACT> \"approveProtocol(address,string)\"", COMPOUND_V3_USDC,  "\"Compound V3 USDC\" --private-key $PRIVATE_KEY");
        console.log("cast send <CONTRACT> \"approveProtocol(address,string)\"", AAVE_V3_POOL,      "\"Aave V3 Pool\" --private-key $PRIVATE_KEY");
    }
}
