import datetime as dt
import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from agentic_os.engine import Engine
from agentic_os.server import make_handler


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Engine(today=dt.date(2026, 11, 16))))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, path, method="GET"):
        req = urllib.request.Request(self.base + path, method=method, data=b"" if method == "POST" else None)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_ui_served(self):
        code, body = self.call("/")
        self.assertEqual(code, 200)
        self.assertIn(b"Agentic OS", body)

    def test_run_then_approve_flow(self):
        code, body = self.call("/api/jobs/cert-expiry/run", "POST")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["status"], "failed")
        appr = json.loads(self.call("/api/approvals")[1])
        aid = [a for a in appr if a["state"] == "pending"][0]["id"]
        self.assertEqual(self.call(f"/api/approvals/{aid}/reject", "POST")[0], 200)
        self.assertEqual(self.call(f"/api/approvals/{aid}/approve", "POST")[0], 409)

    def test_unknown_and_traversal(self):
        self.assertEqual(self.call("/api/jobs/nope/run", "POST")[0], 404)
        self.assertEqual(self.call("/../engine.py")[0], 404)
