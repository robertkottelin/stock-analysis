"""Local server for the universe screener dashboard — static files + refresh API.

Serves the repo root so dashboard/screener.html can fetch fresh data, and
exposes a small API the dashboard's Refresh button uses to re-run
utils/universe_screener.py and stream progress:

  GET  /                      → redirect to /dashboard/screener.html
  GET  /api/status            → data/screener_refresh_status.json + liveness
  POST /api/refresh           → spawn universe_screener.py (409 if already running)
  POST /api/refresh?clear=1   → same, with --clear-cache (full refetch)

Usage:
    python utils/screener_server.py               # http://127.0.0.1:8765, opens browser
    python utils/screener_server.py --port 9000 --no-open

Standard library only. Binds to localhost.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from paths import ROOT, DATA_DIR  # noqa: E402

STATUS_PATH = os.path.join(DATA_DIR, "screener_refresh_status.json")
LOG_PATH = os.path.join(DATA_DIR, "screener_refresh.log")

_proc_lock = threading.Lock()
_proc: subprocess.Popen | None = None


def _read_status() -> dict:
    try:
        with open(STATUS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _refresh_running() -> bool:
    with _proc_lock:
        if _proc is not None and _proc.poll() is None:
            return True
    st = _read_status()
    if st.get("running"):
        # a run started outside this server counts too, unless it looks dead
        try:
            upd = time.mktime(time.strptime(st.get("updated", ""), "%Y-%m-%dT%H:%M:%S"))
            return time.time() - upd < 180
        except Exception:
            return False
    return False


def _start_refresh(clear: bool) -> None:
    global _proc
    cmd = [sys.executable, os.path.join(HERE, "universe_screener.py"), "--workers", "6"]
    if clear:
        cmd.append("--clear-cache")
    log = open(LOG_PATH, "a", encoding="utf-8")
    log.write(f"\n===== refresh started {time.strftime('%Y-%m-%d %H:%M:%S')} "
              f"(clear={clear}) =====\n")
    log.flush()
    with _proc_lock:
        _proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):          # keep the console quiet
        if "/api/" not in (args[0] if args else ""):
            return

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/dashboard/screener.html")
            self.end_headers()
            return
        if path == "/api/status":
            st = _read_status()
            st["process_alive"] = _refresh_running()
            if st.get("running") and not st["process_alive"]:
                st["running"] = False
                st["stalled"] = True
            self._json(200, st)
            return
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/refresh":
            self._json(404, {"error": "unknown endpoint"})
            return
        if _refresh_running():
            self._json(409, {"started": False, "running": True})
            return
        clear = urllib.parse.parse_qs(parsed.query).get("clear", ["0"])[0] == "1"
        _start_refresh(clear)
        self._json(200, {"started": True, "clear": clear})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/dashboard/screener.html"
    print(f"Nordic screener server → {url}   (Ctrl-C to stop)")
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    return 0


if __name__ == "__main__":
    sys.exit(main())
