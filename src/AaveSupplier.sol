// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./interfaces/IAavePool.sol";
import "./interfaces/IWETH.sol";
import "./interfaces/IERC20.sol";

/**
 * @title AaveSupplier
 * @notice Contract to interact with Aave V3 for yield farming
 * @dev Allows depositing and withdrawing ERC20 tokens and ETH to/from Aave
 */
contract AaveSupplier {
    // Events
    event DepositedERC20(address indexed asset, uint256 amount);
    event WithdrawnERC20(address indexed asset, uint256 amount, address indexed recipient);
    event DepositedETH(uint256 amount);
    event WithdrawnETH(uint256 amount, address indexed recipient);

    // Aave Pool
    IAavePool public immutable aavePool;

    // WETH address
    IWETH public immutable weth;

    // Owner (for access control)
    address public owner;

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    /**
     * @notice Constructor
     * @param _aavePool Address of Aave V3 Pool
     * @param _weth Address of WETH
     */
    constructor(address _aavePool, address _weth) {
        require(_aavePool != address(0), "Invalid pool address");
        require(_weth != address(0), "Invalid WETH address");

        aavePool = IAavePool(_aavePool);
        weth = IWETH(_weth);
        owner = msg.sender;
    }

    /**
     * @notice Receive ETH
     */
    receive() external payable {}

    /**
     * @notice Deposit ERC20 tokens to Aave
     * @param asset Address of the ERC20 token
     * @param amount Amount to deposit
     */
    function depositERC20(address asset, uint256 amount) external onlyOwner {
        require(asset != address(0), "Invalid asset");
        require(amount > 0, "Amount must be > 0");

        // Transfer tokens from caller to this contract if not already here
        uint256 balance = IERC20(asset).balanceOf(address(this));
        if (balance < amount) {
            IERC20(asset).transferFrom(msg.sender, address(this), amount - balance);
        }

        // Approve Aave Pool to spend tokens
        IERC20(asset).approve(address(aavePool), amount);

        // Supply to Aave
        aavePool.supply(asset, amount, address(this), 0);

        emit DepositedERC20(asset, amount);
    }

    /**
     * @notice Withdraw ERC20 tokens from Aave
     * @param asset Address of the ERC20 token
     * @param amount Amount to withdraw (use type(uint256).max for max)
     * @param recipient Address to send the withdrawn tokens to
     */
    function withdrawERC20(address asset, uint256 amount, address recipient) external onlyOwner {
        require(asset != address(0), "Invalid asset");
        require(recipient != address(0), "Invalid recipient");

        // Withdraw from Aave
        uint256 withdrawn = aavePool.withdraw(asset, amount, recipient);

        emit WithdrawnERC20(asset, withdrawn, recipient);
    }

    /**
     * @notice Deposit ETH to Aave (wraps to WETH first)
     * @dev Wraps msg.value + contract balance to WETH and deposits to Aave
     */
    function depositEth() external payable onlyOwner {
        uint256 ethBalance = address(this).balance;
        require(ethBalance > 0, "No ETH to deposit");

        // Wrap ETH to WETH
        weth.deposit{value: ethBalance}();

        // Approve Aave Pool
        weth.approve(address(aavePool), ethBalance);

        // Supply WETH to Aave
        aavePool.supply(address(weth), ethBalance, address(this), 0);

        emit DepositedETH(ethBalance);
    }

    /**
     * @notice Withdraw ETH from Aave (unwraps WETH)
     * @param recipient Address to send the ETH to
     * @return Amount of ETH withdrawn
     */
    function withdrawEth(address recipient) external onlyOwner returns (uint256) {
        require(recipient != address(0), "Invalid recipient");

        // Withdraw all WETH from Aave to this contract
        uint256 withdrawn = aavePool.withdraw(address(weth), type(uint256).max, address(this));

        if (withdrawn > 0) {
            // Unwrap WETH to ETH
            weth.withdraw(withdrawn);

            // Send ETH to recipient
            (bool success, ) = recipient.call{value: withdrawn}("");
            require(success, "ETH transfer failed");
        }

        emit WithdrawnETH(withdrawn, recipient);
        return withdrawn;
    }

    /**
     * @notice Get the aToken balance (supplied amount + interest)
     * @param aToken Address of the aToken
     * @return Balance of aTokens
     */
    function getATokenBalance(address aToken) external view returns (uint256) {
        return IERC20(aToken).balanceOf(address(this));
    }

    /**
     * @notice Get user account data from Aave
     * @return totalCollateralBase Total collateral in base currency
     * @return totalDebtBase Total debt in base currency
     * @return availableBorrowsBase Available borrows in base currency
     * @return currentLiquidationThreshold Current liquidation threshold
     * @return ltv Loan to value
     * @return healthFactor Health factor
     */
    function getAccountData() external view returns (
        uint256 totalCollateralBase,
        uint256 totalDebtBase,
        uint256 availableBorrowsBase,
        uint256 currentLiquidationThreshold,
        uint256 ltv,
        uint256 healthFactor
    ) {
        return aavePool.getUserAccountData(address(this));
    }

    /**
     * @notice Transfer ownership
     * @param newOwner New owner address
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Invalid new owner");
        owner = newOwner;
    }

    /**
     * @notice Emergency withdraw of any ERC20 token
     * @param token Token address
     * @param to Recipient address
     */
    function emergencyWithdraw(address token, address to) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        if (balance > 0) {
            IERC20(token).transfer(to, balance);
        }
    }
}
