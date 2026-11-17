"""Storage, the supervisor agent and the scheduler."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .jobs import DATA_DIR, JOBS, JobResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL, started TEXT NOT NULL, finished TEXT,
  status TEXT, summary TEXT, findings TEXT, log TEXT, review TEXT);
CREATE TABLE IF NOT EXISTS approvals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL, job_id TEXT NOT NULL,
  kind TEXT, target TEXT, reason TEXT, risk TEXT,
  state TEXT NOT NULL DEFAULT 'pending', decided_by TEXT, decided_at TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS settings (job_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL);
"""


def now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


class Supervisor:
    """The agent that watches every run.

    It reads the job's result, writes a short plain-English review and decides
    what happens to each proposed change. This version is rule-based so the
    demo runs offline; swap `review` for a call to a language model if you
    want richer write-ups. The safety rule stays the same either way:
    nothing is changed without a human approval.
    """

    def review(self, job_name: str, result: JobResult) -> str:
        if result.status == "ok":
            return f"{job_name} looks healthy. No action needed."
        high = [f for f in result.findings if f.get("level") == "high"]
        parts = [f"{job_name}: {result.summary}."]
        if high:
            parts.append(f"{len(high)} item(s) are urgent and should be handled today.")
        if result.actions:
            parts.append(f"I have queued {len(result.actions)} change(s) for approval; "
                         "nothing has been changed yet.")
        return " ".join(parts)


class Engine:
    def __init__(self, db_path: str = ":memory:", today: Optional[dt.date] = None,
                 data_dir: Path = DATA_DIR):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()
        self.today = today or dt.date.today()
        self.data_dir = data_dir
        self.supervisor = Supervisor()
        self._stop = threading.Event()

    # ---- jobs -------------------------------------------------------------
    def is_enabled(self, job_id: str) -> bool:
        row = self.db.execute("SELECT enabled FROM settings WHERE job_id=?", (job_id,)).fetchone()
        return bool(row["enabled"]) if row else True

    def set_enabled(self, job_id: str, enabled: bool) -> None:
        if job_id not in JOBS:
            raise KeyError(job_id)
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (job_id, int(enabled)))
            self.db.commit()

    def list_jobs(self):
        out = []
        for j in JOBS.values():
            last = self.db.execute(
                "SELECT id,status,finished,summary FROM runs WHERE job_id=? ORDER BY id DESC LIMIT 1",
                (j.id,)).fetchone()
            out.append({"id": j.id, "name": j.name, "description": j.description,
                        "every_minutes": j.every_minutes, "enabled": self.is_enabled(j.id),
                        "last_run": dict(last) if last else None})
        return out

    def run_job(self, job_id: str) -> int:
        job = JOBS[job_id]
        started = now()
        try:
            result = job.run(self.today, self.data_dir)
        except Exception as exc:  # a broken job must not crash the app
            result = JobResult("failed", f"Job crashed: {exc}", log=[repr(exc)])
        review = self.supervisor.review(job.name, result)
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO runs (job_id,started,finished,status,summary,findings,log,review)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (job_id, started, now(), result.status, result.summary,
                 json.dumps(result.findings), json.dumps(result.log), review))
            run_id = cur.lastrowid
            for a in result.actions:
                # Don't queue the same change twice while one is still waiting.
                dup = self.db.execute(
                    "SELECT 1 FROM approvals WHERE kind=? AND target=? AND state='pending'",
                    (a.kind, a.target)).fetchone()
                if not dup:
                    self.db.execute(
                        "INSERT INTO approvals (run_id,job_id,kind,target,reason,risk)"
                        " VALUES (?,?,?,?,?,?)", (run_id, job_id, *asdict(a).values()))
            self.db.commit()
        return run_id

    # ---- runs -------------------------------------------------------------
    def list_runs(self, job_id: Optional[str] = None, limit: int = 50):
        q, args = "SELECT * FROM runs", []
        if job_id:
            q, args = q + " WHERE job_id=?", [job_id]
        rows = self.db.execute(q + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
        return [self._run(r) for r in rows]

    def get_run(self, run_id: int):
        r = self.db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return self._run(r) if r else None

    @staticmethod
    def _run(r):
        d = dict(r)
        d["findings"] = json.loads(d["findings"] or "[]")
        d["log"] = json.loads(d["log"] or "[]")
        return d

    # ---- approvals --------------------------------------------------------
    def list_approvals(self, state: Optional[str] = None):
        q, args = "SELECT * FROM approvals", ()
        if state:
            q, args = q + " WHERE state=?", (state,)
        return [dict(r) for r in self.db.execute(q + " ORDER BY id DESC", args)]

    def decide(self, approval_id: int, approve: bool, who: str = "demo-admin") -> dict:
        with self.lock:
            row = self.db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if not row:
                raise KeyError(approval_id)
            if row["state"] != "pending":
                raise ValueError("already decided")
            state = "approved" if approve else "rejected"
            # Demo mode: approved changes are only simulated and written to the note.
            note = (f"Simulated: {row['kind']} on {row['target']}" if approve
                    else "Rejected; no change made")
            self.db.execute("UPDATE approvals SET state=?,decided_by=?,decided_at=?,note=? WHERE id=?",
                            (state, who, now(), note, approval_id))
            self.db.commit()
        return dict(self.db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone())

    def stats(self):
        q = lambda s, *a: self.db.execute(s, a).fetchone()[0]
        return {"jobs": len(JOBS), "runs": q("SELECT COUNT(*) FROM runs"),
                "pending": q("SELECT COUNT(*) FROM approvals WHERE state='pending'"),
                "failed": q("SELECT COUNT(*) FROM runs WHERE status='failed'")}

    # ---- scheduler --------------------------------------------------------
    def due_jobs(self, at: Optional[dt.datetime] = None):
        at = at or dt.datetime.now()
        due = []
        for j in JOBS.values():
            if not self.is_enabled(j.id):
                continue
            last = self.db.execute("SELECT started FROM runs WHERE job_id=? ORDER BY id DESC LIMIT 1",
                                   (j.id,)).fetchone()
            if not last or at - dt.datetime.fromisoformat(last["started"]) >= dt.timedelta(minutes=j.every_minutes):
                due.append(j.id)
        return due

    def tick(self):
        for job_id in self.due_jobs():
            self.run_job(job_id)

    def start_scheduler(self, every_seconds: int = 30):
        def loop():
            while not self._stop.is_set():
                self.tick()
                self._stop.wait(every_seconds)
        threading.Thread(target=loop, daemon=True).start()

    def stop(self):
        self._stop.set()
