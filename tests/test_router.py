"""Unit and end-to-end tests for OrbitUSDG Arbitrum Stylus + Solidity Router."""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.router_engine import OrbitUSDGRouterEngine
from backend.server import create_server


class TestOrbitUSDGRouter(unittest.TestCase):
    """Tests Solidity/Stylus verification, USDG intent quoting, and slippage guard."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.srv = create_server(port=0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_solidity_and_stylus_contracts_verified(self) -> None:
        eng = OrbitUSDGRouterEngine()
        v = eng.verify_contracts()
        self.assertTrue(v["solidityValid"])
        self.assertTrue(v["stylusValid"])
        self.assertIn(4663, v["supportedChains"])
        self.assertIn(42161, v["supportedChains"])

    def test_intent_lifecycle_and_slippage_guard(self) -> None:
        eng = OrbitUSDGRouterEngine()
        it = eng.create_intent(
            maker="0x1111",
            recipient="0x2222",
            src_chain_id=42161,
            dst_chain_id=4663,
            amount_in_usdg=1000.0,
            slippage_tolerance_bps=50,
            solver_fee_bps=10,
        )
        self.assertEqual(it.status, "OPEN")
        settled = eng.settle_intent(it.intent_id)
        self.assertEqual(settled.status, "SETTLED")
        self.assertTrue(settled.settlement_proof_hex.startswith("0x"))

        # Zero slippage tolerance with non-zero fee must fail SlippageExceeded on settle.
        tight = eng.create_intent(
            maker="0x1111",
            recipient="0x2222",
            src_chain_id=42161,
            dst_chain_id=4663,
            amount_in_usdg=5000.0,
            slippage_tolerance_bps=0,
            solver_fee_bps=20,
        )
        with self.assertRaises(ValueError):
            eng.settle_intent(tight.intent_id)

    def test_http_api_create_and_settle(self) -> None:
        c_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/create_intent",
            data=json.dumps({"srcChainId": 42161, "dstChainId": 4663, "amountInUsdg": 1200.0}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(c_req, timeout=5) as r1:
            d1 = json.loads(r1.read().decode("utf-8"))
        iid = d1["intent"]["intent_id"]

        s_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/settle_intent",
            data=json.dumps({"intentId": iid}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(s_req, timeout=5) as r2:
            d2 = json.loads(r2.read().decode("utf-8"))
        self.assertEqual(d2["intent"]["status"], "SETTLED")


if __name__ == "__main__":
    unittest.main()
