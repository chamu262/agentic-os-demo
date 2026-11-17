"""Small JSON API plus the desktop-style web UI. Standard library only."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engine import Engine
from .jobs import JOBS

STATIC = Path(__file__).parent / "static"
DEMO_DATE = dt.date(2026, 11, 16)  # the made-up data is written relative to this day
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}


def make_handler(engine: Engine):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the console quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            p = self.path.split("?")[0]
            if p == "/api/jobs":
                return self._send(200, engine.list_jobs())
            if p == "/api/stats":
                return self._send(200, engine.stats())
            if p == "/api/runs":
                q = dict(x.split("=", 1) for x in self.path.partition("?")[2].split("&") if "=" in x)
                return self._send(200, engine.list_runs(q.get("job")))
            m = re.fullmatch(r"/api/runs/(\d+)", p)
            if m:
                run = engine.get_run(int(m.group(1)))
                return self._send(200, run) if run else self._send(404, {"error": "not found"})
            if p == "/api/approvals":
                return self._send(200, engine.list_approvals())
            f = (STATIC / ("index.html" if p == "/" else p.lstrip("/"))).resolve()
            if f.is_file() and STATIC.resolve() in f.parents:
                return self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
            self._send(404, {"error": "not found"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
            m = re.fullmatch(r"/api/jobs/([\w-]+)/(run|enable|disable)", self.path)
            if m:
                job_id, op = m.groups()
                if job_id not in JOBS:
                    return self._send(404, {"error": "unknown job"})
                if op == "run":
                    return self._send(200, engine.get_run(engine.run_job(job_id)))
                engine.set_enabled(job_id, op == "enable")
                return self._send(200, {"ok": True})
            m = re.fullmatch(r"/api/approvals/(\d+)/(approve|reject)", self.path)
            if m:
                try:
                    return self._send(200, engine.decide(int(m.group(1)), m.group(2) == "approve",
                                                         body.get("by", "demo-admin")))
                except KeyError:
                    return self._send(404, {"error": "not found"})
                except ValueError as e:
                    return self._send(409, {"error": str(e)})
            self._send(404, {"error": "not found"})

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run Agentic OS on demo data.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--db", default=":memory:", help="SQLite file (default: in memory)")
    a = ap.parse_args(argv)
    engine = Engine(a.db, today=DEMO_DATE)
    engine.start_scheduler()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(engine))
    print(f"Agentic OS running on http://127.0.0.1:{a.port}  (demo data, Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        engine.stop()
