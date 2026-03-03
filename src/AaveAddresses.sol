// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AaveAddresses
 * @notice Contains addresses for Aave V3 protocol on different networks
 */
library AaveAddresses {
    // Ethereum Mainnet Addresses
    address constant MAINNET_POOL = 0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2;
    address constant MAINNET_POOL_ADDRESSES_PROVIDER = 0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e;
    address constant MAINNET_WETH = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    address constant MAINNET_WETH_GATEWAY = 0x893411580e590D62dDBca8a703d61Cc4A8c7b2b9;
    address constant MAINNET_USDC = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address constant MAINNET_USDT = 0xdAC17F958D2ee523a2206206994597C13D831ec7;
    address constant MAINNET_DAI = 0x6B175474E89094C44Da98b954EedeAC495271d0F;
    address constant MAINNET_AWETH = 0x4d5F47FA6A74757f35C14fD3a6Ef8E3C9BC514E8;

    // Sepolia Testnet Addresses
    address constant SEPOLIA_POOL = 0x6Ae43d3271ff6888e7Fc43Fd7321a503ff738951;
    address constant SEPOLIA_POOL_ADDRESSES_PROVIDER = 0x012bAC54348C0E635dCAc9D5FB99f06F24136C9A;
    address constant SEPOLIA_WETH = 0xC558DBdd856501FCd9aaF1E62eae57A9F0629a3c;
    address constant SEPOLIA_WETH_GATEWAY = 0x387d311e47e80b498169e6fb51d3193167d89F7D;
    address constant SEPOLIA_USDC = 0x94a9D9AC8a22534E3FaCa9F4e7F2E2cf85d5E4C8;
    address constant SEPOLIA_DAI = 0xFF34B3d4Aee8ddCd6F9AFFFB6Fe49bD371b8a357;
}
