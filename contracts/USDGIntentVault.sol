// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

interface IERC20Minimal {
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
    function transfer(address recipient, uint256 amount) external returns (bool);
}

interface IStylusRouteVerifier {
    function computeOptimalOut(
        uint256 amountIn,
        uint256 reserveIn,
        uint256 reserveOut,
        uint16 feeBps
    ) external view returns (uint256 amountOut, uint256 priceImpactBps);
}

/// @title USDGIntentVault
/// @notice Cross-chain Paxos USDG Intent Escrow & Settlement Vault connecting Arbitrum and Robinhood Chain (4663).
contract USDGIntentVault {
    uint256 public constant ARBITRUM_ONE_CHAIN_ID = 42161;
    uint256 public constant ROBINHOOD_CHAIN_ID = 4663;
    uint16 public constant MAX_SOLVER_FEE_BPS = 25;

    IERC20Minimal public immutable usdgToken;
    IStylusRouteVerifier public immutable stylusVerifier;
    address public immutable admin;

    enum IntentStatus {
        None,
        Open,
        Settled,
        Refunded
    }

    struct CrossChainIntent {
        address maker;
        address recipient;
        uint256 srcChainId;
        uint256 dstChainId;
        uint256 amountInUsdg;
        uint256 minAmountOutUsdg;
        uint16 solverFeeBps;
        uint64 deadline;
        IntentStatus status;
        bytes32 settlementProof;
    }

    uint256 public nextIntentId;
    uint256 public totalVolumeUsdg;
    mapping(uint256 => CrossChainIntent) public intents;

    event IntentCreated(
        uint256 indexed intentId,
        address indexed maker,
        uint256 srcChainId,
        uint256 dstChainId,
        uint256 amountInUsdg,
        uint256 minAmountOutUsdg
    );
    event IntentSettled(
        uint256 indexed intentId,
        address indexed solver,
        uint256 netAmountOutUsdg,
        bytes32 settlementProof
    );
    event IntentRefunded(uint256 indexed intentId, address indexed maker, uint256 amountReturned);

    error InvalidAmount();
    error FeeTooHigh();
    error InvalidDeadline();
    error InvalidStatus();
    error SlippageExceeded();
    error DeadlineNotExpired();

    constructor(address _usdgToken, address _stylusVerifier) {
        usdgToken = IERC20Minimal(_usdgToken);
        stylusVerifier = IStylusRouteVerifier(_stylusVerifier);
        admin = msg.sender;
    }

    function createUsdgIntent(
        address recipient,
        uint256 dstChainId,
        uint256 amountInUsdg,
        uint256 minAmountOutUsdg,
        uint16 solverFeeBps,
        uint64 deadline
    ) external returns (uint256 intentId) {
        if (amountInUsdg == 0 || recipient == address(0)) revert InvalidAmount();
        if (solverFeeBps > MAX_SOLVER_FEE_BPS) revert FeeTooHigh();
        if (deadline <= block.timestamp) revert InvalidDeadline();

        bool ok = usdgToken.transferFrom(msg.sender, address(this), amountInUsdg);
        require(ok, "USDG transferFrom failed");

        intentId = ++nextIntentId;
        intents[intentId] = CrossChainIntent({
            maker: msg.sender,
            recipient: recipient,
            srcChainId: block.chainid,
            dstChainId: dstChainId,
            amountInUsdg: amountInUsdg,
            minAmountOutUsdg: minAmountOutUsdg,
            solverFeeBps: solverFeeBps,
            deadline: deadline,
            status: IntentStatus.Open,
            settlementProof: bytes32(0)
        });

        totalVolumeUsdg += amountInUsdg;
        emit IntentCreated(intentId, msg.sender, block.chainid, dstChainId, amountInUsdg, minAmountOutUsdg);
    }

    function settleIntentWithStylusQuote(
        uint256 intentId,
        uint256 reserveIn,
        uint256 reserveOut,
        bytes32 settlementProof
    ) external returns (uint256 netOut) {
        CrossChainIntent storage it = intents[intentId];
        if (it.status != IntentStatus.Open) revert InvalidStatus();

        (uint256 quotedOut, ) = stylusVerifier.computeOptimalOut(
            it.amountInUsdg,
            reserveIn,
            reserveOut,
            it.solverFeeBps
        );
        if (quotedOut < it.minAmountOutUsdg) revert SlippageExceeded();

        it.status = IntentStatus.Settled;
        it.settlementProof = settlementProof;
        netOut = quotedOut;

        bool ok = usdgToken.transfer(msg.sender, it.amountInUsdg);
        require(ok, "Solver payout failed");

        emit IntentSettled(intentId, msg.sender, netOut, settlementProof);
    }

    function refundExpiredIntent(uint256 intentId) external {
        CrossChainIntent storage it = intents[intentId];
        if (it.status != IntentStatus.Open) revert InvalidStatus();
        if (block.timestamp <= it.deadline) revert DeadlineNotExpired();

        it.status = IntentStatus.Refunded;
        bool ok = usdgToken.transfer(it.maker, it.amountInUsdg);
        require(ok, "Refund failed");

        emit IntentRefunded(intentId, it.maker, it.amountInUsdg);
    }
}
