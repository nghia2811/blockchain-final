// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title Compound V3 (Comet) interface (subset)
interface IComet {
    /// @notice Supply an asset to the protocol
    function supply(address asset, uint256 amount) external;

    /// @notice Withdraw an asset from the protocol
    function withdraw(address asset, uint256 amount) external;

    /// @notice Get the balance of an account
    function balanceOf(address account) external view returns (uint256);

    /// @notice Get the current supply rate per second
    function getSupplyRate(uint256 utilization) external view returns (uint64);

    /// @notice Get the current utilization ratio
    function getUtilization() external view returns (uint256);

    /// @notice Base token of the Comet market
    function baseToken() external view returns (address);
}
