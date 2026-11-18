#![cfg_attr(not(feature = "export-abi"), no_main)]
extern crate alloc;

use stylus_sdk::{alloy_primitives::U256, prelude::*};

sol_storage! {
    #[entrypoint]
    pub struct StylusRouteVerifier {
        uint256 total_quotes_computed;
    }
}

#[public]
impl StylusRouteVerifier {
    /// Computes constant-product + stable-swap hybrid output and price impact in basis points
    /// for Paxos USDG cross-chain intents between Arbitrum and Robinhood Chain (chainId 4663).
    pub fn compute_optimal_out(
        &self,
        amount_in: U256,
        reserve_in: U256,
        reserve_out: U256,
        fee_bps: u16,
    ) -> (U256, U256) {
        if amount_in.is_zero() || reserve_in.is_zero() || reserve_out.is_zero() || fee_bps > 1000 {
            return (U256::ZERO, U256::from(10_000));
        }

        let bps_denom = U256::from(10_000);
        let net_factor = U256::from(10_000u64 - (fee_bps as u64));
        let amount_in_after_fee = (amount_in * net_factor) / bps_denom;

        // Hybrid stable-curve boost (85% 1:1 peg weight + 15% destination-depth adjustment) for USDG pools.
        let cpmm_num = amount_in_after_fee * reserve_out;
        let cpmm_den = reserve_out + amount_in_after_fee;
        let cpmm_out = cpmm_num / cpmm_den;

        let blended_out = (amount_in_after_fee * U256::from(85) + cpmm_out * U256::from(15)) / U256::from(100);
        let impact_bps = if amount_in_after_fee > blended_out {
            ((amount_in_after_fee - blended_out) * bps_denom) / amount_in_after_fee
        } else {
            U256::ZERO
        };

        (blended_out, impact_bps)
    }
}
