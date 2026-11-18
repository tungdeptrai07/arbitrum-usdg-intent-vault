# OrbitUSDG — Arbitrum Stylus & Solidity Cross-Chain USDG Intent Vault

Submission for **Arbitrum Open House São Paulo: Online Buildathon** on HackQuest (`$115,000 USD` Prize Pool).

## Why OrbitUSDG Fits All Arbitrum Open House Tracks
- **Dual Ecosystem Coverage**: Bridges **Arbitrum One (`42161`) / Arbitrum Sepolia (`421614`)** and **Robinhood Chain (`4663`)** (targeting both the Arbitrum track and the dedicated Robinhood Chain reserved prize pool).
- **Paxos `USDG` Stablecoin Native**: Uses Paxos `USDG` (Global Dollar) as the primary settlement asset with slippage-protected cross-chain intents.
- **Hybrid Solidity + Arbitrum Stylus (Rust) Stack**:
  - `contracts/USDGIntentVault.sol`: Solidity escrow, intent lifecycle (`createUsdgIntent`, `settleIntentWithStylusQuote`, `refundExpiredIntent`), and solver fee cap (`<= 25 bps`).
  - `stylus_rust/src/lib.rs`: Arbitrum Stylus (`stylus-sdk`) Rust verifier computing hybrid stable-curve quotes and price impact in basis points.

## Run & Test Locally
```bash
python -m unittest discover -s tests -v
python backend/server.py
# Open http://127.0.0.1:8094
```
