# OrbitUSDG Router  |  HackQuest Arbitrum Open House ($115,000)

## Slide 1: OrbitUSDG: Arbitrum Stylus & Robinhood Chain USDG Vault
*Cross-chain Paxos USDG Intent Settlement across Arbitrum (42161) & Robinhood Chain (4663)*

- **Dual Track Fit**: Bridges Arbitrum One/Sepolia and Robinhood Chain (4663) with Paxos USDG.
- **Solidity + Stylus**: USDGIntentVault.sol escrow paired with Stylus Rust (lib.rs) quote verifier.
- **Slippage Guard**: Enforces <= 25 bps solver fee cap and deterministic minAmountOut protection.

## Slide 2: Hybrid Solidity + Rust Stylus Architecture
*Gas-efficient stable-curve quoting and verifiable cross-chain intent settlement*

- **Solidity Vault**: createUsdgIntent, settleIntentWithStylusQuote, refundExpiredIntent.
- **Stylus Rust Verifier**: compute_optimal_out blends 85% peg weight + 15% depth curve.
- **Verified QA**: 3/3 unit tests passing (tests/test_router.py) + interactive Web UI.
