import datetime as dt
import unittest

from agentic_os.jobs import JOBS, certificate_expiry, licence_usage, stale_devices

DAY = dt.date(2026, 11, 16)


class JobTests(unittest.TestCase):
    def test_stale_devices_flags_and_proposes(self):
        r = stale_devices(DAY)
        self.assertEqual(r.status, "warning")
        self.assertTrue(all(f["days_silent"] >= 30 for f in r.findings))
        self.assertTrue(all(a.kind == "disable_device" for a in r.actions))
        # only 90+ day devices get a disable proposal
        self.assertEqual(len(r.actions), sum(f["days_silent"] >= 90 for f in r.findings))

    def test_licence_usage_finds_idle_and_full(self):
        issues = {f["issue"] for f in licence_usage(DAY).findings}
        self.assertEqual(issues, {"almost full", "many idle seats"})

    def test_cert_expiry_fails_when_urgent(self):
        r = certificate_expiry(DAY)
        self.assertEqual(r.status, "failed")
        self.assertTrue(any(a.risk == "high" for a in r.actions))

    def test_cert_expiry_ok_far_in_past(self):
        r = certificate_expiry(dt.date(2020, 1, 1))
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.actions, [])

    def test_all_jobs_registered(self):
        self.assertEqual(set(JOBS), {"stale-devices", "licence-usage", "cert-expiry"})
