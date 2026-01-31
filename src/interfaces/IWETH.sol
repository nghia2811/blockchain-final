// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IWETH
 * @notice Interface for Wrapped Ether
 */
interface IWETH {
    function deposit() external payable;
    function withdraw(uint256) external;
    function balanceOf(address) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}
