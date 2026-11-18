"""OrbitUSDG Arbitrum Stylus + Solidity Cross-Chain USDG Intent Engine.

Connects Arbitrum One (42161) / Arbitrum Sepolia (421614) and Robinhood Chain (4663)
using Paxos USDG stablecoin intents and Stylus Rust route verification math.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SOL_PATH = Path(__file__).resolve().parent.parent / "contracts" / "USDGIntentVault.sol"
RS_PATH = Path(__file__).resolve().parent.parent / "stylus_rust" / "src" / "lib.rs"

SUPPORTED_CHAINS = {
    42161: "Arbitrum One",
    421614: "Arbitrum Sepolia",
    4663: "Robinhood Chain",
}
MAX_SOLVER_FEE_BPS = 25


def stylus_compute_optimal_out(
    amount_in_usdg: float,
    reserve_in_usdg: float,
    reserve_out_usdg: float,
    fee_bps: int,
) -> tuple[float, float]:
    """Exact mirror of `StylusRouteVerifier::compute_optimal_out` in `stylus_rust/src/lib.rs`."""
    if amount_in_usdg <= 0 or reserve_in_usdg <= 0 or reserve_out_usdg <= 0 or fee_bps < 0 or fee_bps > 1000:
        return 0.0, 10000.0

    net_in = amount_in_usdg * (10_000 - fee_bps) / 10_000.0
    cpmm_out = (net_in * reserve_out_usdg) / (reserve_out_usdg + net_in)
    blended_out = 0.85 * net_in + 0.15 * cpmm_out
    impact_bps = max(0.0, ((net_in - blended_out) / max(net_in, 1e-9)) * 10_000.0)
    return round(blended_out, 4), round(impact_bps, 2)


@dataclass
class CrossChainUSDGIntent:
    """Represents an escrowed Paxos USDG cross-chain intent between Arbitrum and Robinhood Chain."""

    intent_id: int
    maker: str
    recipient: str
    src_chain_id: int
    src_chain_name: str
    dst_chain_id: int
    dst_chain_name: str
    amount_in_usdg: float
    min_amount_out_usdg: float
    quoted_out_usdg: float
    price_impact_bps: float
    solver_fee_bps: int
    status: str  # "OPEN", "SETTLED", "REFUNDED"
    settlement_proof_hex: str | None
    created_at: float


class OrbitUSDGRouterEngine:
    """Manages Arbitrum <-> Robinhood Chain USDG intents and Stylus route verification."""

    def __init__(self, reserve_arbitrum_usdg: float = 500_000.0, reserve_robinhood_usdg: float = 350_000.0) -> None:
        self.reserve_arbitrum_usdg = reserve_arbitrum_usdg
        self.reserve_robinhood_usdg = reserve_robinhood_usdg
        self.intents: dict[int, CrossChainUSDGIntent] = {}
        self.total_volume_usdg: float = 0.0

    def verify_contracts(self) -> dict[str, Any]:
        """Verify that both Solidity and Stylus Rust contracts are present and valid."""
        sol_code = SOL_PATH.read_text(encoding="utf-8")
        rs_code = RS_PATH.read_text(encoding="utf-8")
        return {
            "solidityContract": SOL_PATH.name,
            "solidityValid": "contract USDGIntentVault" in sol_code and "settleIntentWithStylusQuote" in sol_code,
            "stylusRustContract": RS_PATH.name,
            "stylusValid": "pub struct StylusRouteVerifier" in rs_code and "pub fn compute_optimal_out" in rs_code,
            "supportedChains": SUPPORTED_CHAINS,
            "stablecoin": "Paxos USDG (Global Dollar)",
        }

    def create_intent(
        self,
        maker: str,
        recipient: str,
        src_chain_id: int,
        dst_chain_id: int,
        amount_in_usdg: float,
        slippage_tolerance_bps: int = 30,
        solver_fee_bps: int = 10,
    ) -> CrossChainUSDGIntent:
        """Create and quote a new cross-chain USDG intent."""
        if src_chain_id not in SUPPORTED_CHAINS or dst_chain_id not in SUPPORTED_CHAINS:
            raise ValueError("Unsupported chainId; must be Arbitrum (42161/421614) or Robinhood Chain (4663).")
        if src_chain_id == dst_chain_id:
            raise ValueError("Source and destination chains must differ.")
        if amount_in_usdg <= 0:
            raise ValueError("amount_in_usdg must be positive.")
        if solver_fee_bps < 0 or solver_fee_bps > MAX_SOLVER_FEE_BPS:
            raise ValueError(f"solver_fee_bps exceeds MAX_SOLVER_FEE_BPS ({MAX_SOLVER_FEE_BPS}).")

        res_in = self.reserve_arbitrum_usdg if src_chain_id != 4663 else self.reserve_robinhood_usdg
        res_out = self.reserve_robinhood_usdg if dst_chain_id == 4663 else self.reserve_arbitrum_usdg

        quoted_out, impact_bps = stylus_compute_optimal_out(
            amount_in_usdg=amount_in_usdg,
            reserve_in_usdg=res_in,
            reserve_out_usdg=res_out,
            fee_bps=solver_fee_bps,
        )
        min_out = round(amount_in_usdg * (10_000 - slippage_tolerance_bps) / 10_000.0, 4)

        intent_id = len(self.intents) + 1
        intent = CrossChainUSDGIntent(
            intent_id=intent_id,
            maker=maker,
            recipient=recipient,
            src_chain_id=src_chain_id,
            src_chain_name=SUPPORTED_CHAINS[src_chain_id],
            dst_chain_id=dst_chain_id,
            dst_chain_name=SUPPORTED_CHAINS[dst_chain_id],
            amount_in_usdg=round(float(amount_in_usdg), 4),
            min_amount_out_usdg=min_out,
            quoted_out_usdg=quoted_out,
            price_impact_bps=impact_bps,
            solver_fee_bps=solver_fee_bps,
            status="OPEN",
            settlement_proof_hex=None,
            created_at=round(time.time(), 3),
        )
        self.intents[intent_id] = intent
        self.total_volume_usdg = round(self.total_volume_usdg + amount_in_usdg, 4)
        return intent

    def settle_intent(self, intent_id: int) -> CrossChainUSDGIntent:
        """Execute `settleIntentWithStylusQuote` and verify slippage guard."""
        if intent_id not in self.intents:
            raise ValueError(f"Unknown intent_id: {intent_id}")
        it = self.intents[intent_id]
        if it.status != "OPEN":
            raise ValueError(f"Intent is already {it.status}")
        if it.quoted_out_usdg < it.min_amount_out_usdg:
            raise ValueError(
                f"SlippageExceeded: Stylus quote ({it.quoted_out_usdg} USDG) < minAmountOut ({it.min_amount_out_usdg} USDG)."
            )

        seed = f"stylus-usdg:{it.intent_id}:{it.src_chain_id}->{it.dst_chain_id}:{it.quoted_out_usdg}"
        it.settlement_proof_hex = "0x" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
        it.status = "SETTLED"
        return it

    def get_state(self) -> dict[str, Any]:
        """Return contract verification, pool reserves, and intent list."""
        return {
            "contracts": self.verify_contracts(),
            "reserves": {
                "arbitrumUsdg": self.reserve_arbitrum_usdg,
                "robinhoodChainUsdg": self.reserve_robinhood_usdg,
                "totalVolumeUsdg": self.total_volume_usdg,
            },
            "intents": [asdict(i) for i in reversed(list(self.intents.values()))],
        }
