import datetime as dt
import unittest

from agentic_os.engine import Engine
from agentic_os.jobs import JOBS, JobResult, Job

DAY = dt.date(2026, 11, 16)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.e = Engine(today=DAY)

    def test_run_records_run_review_and_approvals(self):
        rid = self.e.run_job("cert-expiry")
        run = self.e.get_run(rid)
        self.assertEqual(run["status"], "failed")
        self.assertIn("approval", run["review"])
        self.assertTrue(self.e.list_approvals("pending"))

    def test_no_duplicate_pending_approvals(self):
        self.e.run_job("stale-devices")
        n = len(self.e.list_approvals("pending"))
        self.e.run_job("stale-devices")
        self.assertEqual(len(self.e.list_approvals("pending")), n)

    def test_approve_and_reject(self):
        self.e.run_job("licence-usage")
        a, *rest = self.e.list_approvals("pending")
        done = self.e.decide(a["id"], True, "tester")
        self.assertEqual(done["state"], "approved")
        self.assertTrue(done["note"].startswith("Simulated"))
        with self.assertRaises(ValueError):
            self.e.decide(a["id"], False)
        with self.assertRaises(KeyError):
            self.e.decide(9999, True)

    def test_scheduler_due_and_pause(self):
        self.assertEqual(set(self.e.due_jobs()), set(JOBS))
        self.e.set_enabled("licence-usage", False)
        self.e.tick()
        self.assertEqual(self.e.due_jobs(), [])
        self.assertEqual({r["job_id"] for r in self.e.list_runs()}, {"stale-devices", "cert-expiry"})
        later = dt.datetime.now() + dt.timedelta(minutes=31)
        self.assertEqual(self.e.due_jobs(later), ["cert-expiry"])

    def test_crashing_job_is_recorded_not_raised(self):
        def boom(today, data_dir):
            raise RuntimeError("demo failure")
        JOBS["boom"] = Job("boom", "Boom", "", 5, boom)
        try:
            run = self.e.get_run(self.e.run_job("boom"))
            self.assertEqual(run["status"], "failed")
            self.assertIn("demo failure", run["summary"])
        finally:
            del JOBS["boom"]

    def test_stats(self):
        self.e.tick()
        s = self.e.stats()
        self.assertEqual(s["runs"], 3)
        self.assertGreater(s["pending"], 0)
