"""Demo jobs. Each job reads made-up data and returns a JobResult.

A job never changes anything itself. If it wants a change made (for example
"disable this stale device"), it returns a *proposed action*. The supervisor
decides whether that action needs a human to approve it first.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List

DATA_DIR = Path(__file__).parent / "demo_data"


@dataclass
class ProposedAction:
    kind: str          # e.g. "disable_device"
    target: str        # what it acts on
    reason: str
    risk: str = "low"  # low | medium | high


@dataclass
class JobResult:
    status: str                      # ok | warning | failed
    summary: str
    findings: List[dict] = field(default_factory=list)
    actions: List[ProposedAction] = field(default_factory=list)
    log: List[str] = field(default_factory=list)


@dataclass
class Job:
    id: str
    name: str
    description: str
    every_minutes: int
    run: Callable[[dt.date, Path], JobResult]


def _load(data_dir: Path, name: str):
    with open(data_dir / name, encoding="utf-8") as fh:
        return json.load(fh)


def stale_devices(today: dt.date, data_dir: Path = DATA_DIR) -> JobResult:
    """Find devices that have not checked in for a long time."""
    devices = _load(data_dir, "devices.json")
    res = JobResult("ok", "")
    res.log.append(f"Loaded {len(devices)} devices")
    for d in devices:
        days = (today - dt.date.fromisoformat(d["last_seen"])).days
        if days >= 90:
            res.findings.append({**d, "days_silent": days, "level": "high"})
            res.actions.append(ProposedAction("disable_device", d["device"],
                                              f"Not seen for {days} days", "medium"))
        elif days >= 30:
            res.findings.append({**d, "days_silent": days, "level": "medium"})
    res.log.append(f"{len(res.findings)} devices silent for 30+ days")
    if res.findings:
        res.status = "warning"
    res.summary = (f"{len(res.findings)} of {len(devices)} devices silent 30+ days; "
                   f"{len(res.actions)} proposed for disabling")
    return res


def licence_usage(today: dt.date, data_dir: Path = DATA_DIR) -> JobResult:
    """Spot licences that are nearly full or largely unused."""
    rows = _load(data_dir, "licences.json")
    res = JobResult("ok", "")
    for r in rows:
        free = r["seats"] - r["assigned"]
        idle = r["assigned"] - r["active_30d"]
        res.log.append(f"{r['product']}: {free} free, {idle} idle")
        if free <= max(1, r["seats"] // 50):
            res.findings.append({**r, "issue": "almost full", "free": free, "level": "medium"})
        if r["assigned"] and idle / r["assigned"] >= 0.3:
            res.findings.append({**r, "issue": "many idle seats", "idle": idle, "level": "low"})
            res.actions.append(ProposedAction("reclaim_seats", r["product"],
                                              f"{idle} seats unused for 30 days", "low"))
    if res.findings:
        res.status = "warning"
    res.summary = f"{len(rows)} products checked, {len(res.findings)} need attention"
    return res


def certificate_expiry(today: dt.date, data_dir: Path = DATA_DIR) -> JobResult:
    """Warn about TLS certificates that expire soon."""
    certs = _load(data_dir, "certificates.json")
    res = JobResult("ok", "")
    for c in certs:
        left = (dt.date.fromisoformat(c["expires"]) - today).days
        level = "high" if left <= 7 else "medium" if left <= 30 else None
        res.log.append(f"{c['host']} expires in {left} days")
        if level:
            res.findings.append({**c, "days_left": left, "level": level})
            res.actions.append(ProposedAction("renew_certificate", c["host"],
                                              f"Expires in {left} days",
                                              "high" if left <= 7 else "medium"))
    if any(f["level"] == "high" for f in res.findings):
        res.status = "failed"
    elif res.findings:
        res.status = "warning"
    res.summary = f"{len(res.findings)} of {len(certs)} certificates expire within 30 days"
    return res


JOBS: Dict[str, Job] = {j.id: j for j in [
    Job("stale-devices", "Stale device report",
        "Lists laptops and desktops that stopped checking in.", 60, stale_devices),
    Job("licence-usage", "Licence usage check",
        "Flags products that are nearly full or paying for idle seats.", 240, licence_usage),
    Job("cert-expiry", "Certificate expiry watch",
        "Warns before website certificates run out.", 30, certificate_expiry),
]}
