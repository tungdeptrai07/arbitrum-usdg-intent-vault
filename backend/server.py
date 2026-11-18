"""HTTP server for OrbitUSDG Arbitrum Stylus & Robinhood Chain Router (port 8094)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.router_engine import OrbitUSDGRouterEngine


class OrbitUSDGHTTPHandler(SimpleHTTPRequestHandler):
    """Serves the OrbitUSDG Arbitrum + Robinhood Chain UI and JSON APIs."""

    engine = OrbitUSDGRouterEngine()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._send_json({"status": "ok", "service": "OrbitUSDG Arbitrum Stylus + Robinhood Chain Router"})
            return

        if self.path == "/api/state":
            self._send_json(self.engine.get_state())
            return

        if self.path in {"", "/"}:
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 128_000))
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            if self.path == "/api/create_intent":
                it = self.engine.create_intent(
                    maker=str(data.get("maker", "0x71C...89A")),
                    recipient=str(data.get("recipient", "0x71C...89A")),
                    src_chain_id=int(data.get("srcChainId", 42161)),
                    dst_chain_id=int(data.get("dstChainId", 4663)),
                    amount_in_usdg=float(data.get("amountInUsdg", 1000.0)),
                    slippage_tolerance_bps=int(data.get("slippageBps", 40)),
                    solver_fee_bps=int(data.get("solverFeeBps", 10)),
                )
                self._send_json({"intent": asdict(it), "state": self.engine.get_state()})
                return

            if self.path == "/api/settle_intent":
                it = self.engine.settle_intent(int(data.get("intentId", 1)))
                self._send_json({"intent": asdict(it), "state": self.engine.get_state()})
                return
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8094,
    engine: OrbitUSDGRouterEngine | None = None,
) -> ThreadingHTTPServer:
    """Create the OrbitUSDG HTTP server."""

    class BoundHandler(OrbitUSDGHTTPHandler):
        pass

    BoundHandler.engine = engine or OrbitUSDGRouterEngine()
    return ThreadingHTTPServer((host, port), BoundHandler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8094"))
    srv = create_server(port=port)
    print(f"OrbitUSDG Arbitrum Stylus & Robinhood Chain Router running on http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()
