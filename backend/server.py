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

from models.ann import predict as ann_predict
from models.ann.live_predict import get_fuzzy_inputs_batch

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


def warm_up():
    """Load everything slow before the first request arrives."""
    print("Starting MATLAB and loading the ANN (this takes a moment) ...")
    ann_predict._load_artifacts()                  # loads TensorFlow + model
    engine = get_engine()                          # starts MATLAB
    with _engine_lock:
        engine.evaluateEnergyRisk(100.0, 1.0, nargout=1)   # caches the FIS
    print("Ready.")


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
            household_id = data.get("household_id") or "MAC000002"

            # actual_kwh may be one number or a list (batch).
            raw = data.get("actual_kwh", 0)
            is_batch = isinstance(raw, list)
            readings = [float(v) for v in raw] if is_batch else [float(raw)]

            date_time = None
            if data.get("datetime"):
                date_time = datetime.fromisoformat(str(data["datetime"]).replace("Z", "+00:00"))

            # One ANN run for all readings.
            fuzzy_inputs = get_fuzzy_inputs_batch(household_id, readings, date_time)

            engine = get_engine()
            results = []
            with _engine_lock:
                for actual, (consumption_pct, tariff) in zip(readings, fuzzy_inputs):
                    risk = engine.evaluateEnergyRisk(float(consumption_pct), float(tariff), nargout=1)
                    results.append({
                        "actual_kwh": actual,
                        "consumption_pct": float(consumption_pct),
                        "risk_score": float(risk),
                    })

            tariff = int(fuzzy_inputs[0][1])
            payload = {
                "household_id": household_id,
                "tariff": tariff,
                "tariff_name": TARIFF_NAMES.get(tariff, "Unknown"),
            }
            if is_batch:
                payload["results"] = results
            else:
                payload.update(results[0])   # same shape as before for a single value
            self._json(200, payload)

        except ValueError as error:
            # Bad input, including unknown household IDs.
            self._json(400, {"error": str(error)})
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
    warm_up()
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
