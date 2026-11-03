"""Simple HTTP server bridging the frontend, ANN and MATLAB fuzzy system.

Run from the project root:
    python backend/server.py

Then open http://127.0.0.1:8000 in a browser.
"""

import json
import sys
import threading
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.ann.live_predict import get_fuzzy_inputs

import matlab.engine

FUZZY_DIR = ROOT / "models" / "fuzzy"
FRONTEND_DIR = ROOT / "frontend"

_engine = None
_engine_lock = threading.Lock()


def get_engine():
    """Start MATLAB once and reuse it for every request."""
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = matlab.engine.start_matlab()
            _engine.addpath(str(FUZZY_DIR), nargout=0)
        return _engine


TARIFF_NAMES = {0: "Off-peak", 1: "Normal", 2: "Peak"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_POST(self):
        if self.path != "/api/risk":
            self.send_error(404, "Not found")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            data = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError) as error:
            self._json(400, {"error": "Invalid JSON: %s" % error})
            return

        try:
            actual_kwh = float(data.get("actual_kwh", 0))
            household_id = data.get("household_id") or "MAC000002"
            date_time = None
            if data.get("datetime"):
                date_time = datetime.fromisoformat(str(data["datetime"]).replace("Z", "+00:00"))

            consumption_pct, tariff = get_fuzzy_inputs(household_id, actual_kwh, date_time)

            engine = get_engine()
            with _engine_lock:
                risk = engine.evaluateEnergyRisk(float(consumption_pct), float(tariff), nargout=1)

            self._json(200, {
                "household_id": household_id,
                "actual_kwh": actual_kwh,
                "consumption_pct": float(consumption_pct),
                "tariff": int(tariff),
                "tariff_name": TARIFF_NAMES.get(int(tariff), "Unknown"),
                "risk_score": float(risk),
            })
        except Exception as error:  # noqa: BLE001 - surface any backend error to the UI
            self._json(500, {"error": str(error)})

    def _json(self, status, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):  # keep the console quiet
        pass


def main():
    port = 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("Your Energy Mate running at http://127.0.0.1:%d" % port)
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        global _engine
        if _engine is not None:
            try:
                _engine.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
