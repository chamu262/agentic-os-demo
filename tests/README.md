# `tests/` — automated tests

Run them from the repo root (no installs needed):

```bash
python -m unittest discover -s tests -v
```

The same command runs in GitHub Actions (`.github/workflows/ci.yml`) on every push.

| File | What it checks |
|---|---|
| `test_jobs.py` | Each demo job finds the right items and proposes the right changes; the certificate job reports "ok" when nothing is close to expiring. |
| `test_engine.py` | Runs are saved with a review; the same change is never queued twice; approve/reject works and can't be done twice; the scheduler respects intervals and paused jobs; a crashing job is recorded as failed instead of stopping the app. |
| `test_server.py` | Starts the real web server on a free port and checks the page loads, the run → approve flow over HTTP, unknown jobs return 404, and files outside `static/` can't be read. |
| `__init__.py` | Empty; lets Python treat the folder as a package. |
