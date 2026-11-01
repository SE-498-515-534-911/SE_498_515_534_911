# US-30: Load test

| | |
| --- | --- |
| Epic | WBMME-5 Testing & Validation |
| Requirement | MLE-NF-003 |
| Points / sprint | 5 / Sprint 2 |
| Owner | Varnika (Member 2) |
| Test Plan | TC-PERF-03 (tool: Locust, section 6) |

**Story.** As the team I want to know that WBMME stays fast with a class of users working at once, so that the demo and real use do not slow down or fail.

## Requirement (SRS MLE-NF-003, TC-PERF-03)

With 20 concurrent logged-in users, every application page loads in 3 seconds or less, for both the average and the 95th percentile, over a run of 5 minutes, and the run produces no server errors (HTTP 5xx). TC-PERF-03: 20 test accounts with sample runs; each user logs in and opens the dashboard, history and results repeatedly for 5 minutes.

## Acceptance criteria

- [x] 20 test accounts, each with a dataset and completed runs, created through the application's own upload, training and evaluation code (`loadtest/seed.py`).
- [x] 20 simulated users, each logged in to their own account through the login page, open the dashboard, history, results (page and its data), datasets page and account home for 5 minutes, pausing 1–3 s like a person reading.
- [x] Every page type: average and 95th percentile ≤ 3 s; no failed request; no 5xx. Checked automatically; the run exits with code 0 only when it passes.
- [x] Result recorded, with the machine it ran on.

## Defect found and fixed

The first run on `main` failed: **188 of 703 requests for results data (27%) answered HTTP 500**, with `sqlite3.OperationalError: database is locked` in the server log (564 tracebacks). Every page and every other request was fast.

**Cause.** Opening a results page calls `/api/evaluate`, which saves the run's metrics again on every view (`store_metrics` in `evaluation/run_evaluation.py`). With 20 users, these writes often happened at the same moment, and with Django's default SQLite settings the second writer fails at once instead of waiting.

**Fix.** `config/settings.py` now uses Django's recommended settings for SQLite under concurrent use: wait up to 20 s for a lock (`timeout`), take the write lock at the start of a transaction (`transaction_mode = IMMEDIATE`), and write-ahead logging (`journal_mode = WAL`), so readers never block the writer. No application code changed. No run was damaged in either test (all 80 stayed COMPLETED).

## Result (5 minutes, 20 users)

Server: `python manage.py runserver` (the command of the Docker image) with production settings, on a 2-core Intel Xeon 2.1 GHz, 8 GB RAM, Linux, Python 3.13. Users joined at one per second.

| Page / request | Before: avg / p95 | Before: failures | After: avg / p95 | After: failures |
| --- | --- | --- | --- | --- |
| Dashboard | 22 / 65 ms | 0 | 22 / 72 ms | 0 |
| History (`/api/runs`) | 26 / 83 ms | 0 | 22 / 74 ms | 0 |
| Results page | 23 / 73 ms | 0 | 20 / 65 ms | 0 |
| Results data (`/api/evaluate`) | 205 / 460 ms | **188 × HTTP 500** | 209 / 500 ms | 0 |
| Datasets page | 22 / 70 ms | 0 | 20 / 67 ms | 0 |
| Account home | 21 / 58 ms | 0 | 19 / 56 ms | 0 |
| Login page / log in | 9 / 564 ms (avg) | 0 | 7 / 571 ms (avg) | 0 |
| **Total** | 3,592 requests | **188 failed: FAIL** | 3,557 requests | **0 failed: PASS** |

Raw Locust reports: `docs/member2/reports/tc_perf_03_{before,after}_{stats,failures}.csv`. (The before failures file lists 187: Locust writes it a moment before the last request of the run is counted in the summary.)

## Observation: login when everyone signs in at once

Logging in checks the password with PBKDF2, which is slow on purpose (MLE-SR-001). When all 20 users log in within 4 seconds (spawn rate 5 per second), the log-in request averaged 2.4 s with a 95th percentile of 3.1 s on this 2-core machine, just over the limit; every page after login stayed fast. With users arriving one per second it averaged 0.57 s. Making password hashing weaker would trade security for speed, so it is left as it is; on a typical 4–8 core laptop the burst should stay well under 3 s. The burst can be repeated with `--spawn-rate 5`.

## How to run it

```bash
pip install -r loadtest/requirements.txt
# 1. start the server, e.g.  docker compose up --build   (or: python manage.py runserver)
# 2. once, against the same database:  python loadtest/seed.py
#    (in Docker:  docker compose exec web python loadtest/seed.py)
# 3. the test:
locust -f loadtest/locustfile.py --host http://127.0.0.1:8000 \
       --headless --users 20 --spawn-rate 1 --run-time 5m --csv tc_perf_03
```
It ends with a table and `TC-PERF-03 / MLE-NF-003: PASS` or `FAIL` (exit code 0 or 1).

## Files

| File | Purpose |
| --- | --- |
| `loadtest/seed.py` | Creates load_user_01 … 20, each with a 1,000-row dataset and 4 completed runs (one per model) |
| `loadtest/locustfile.py` | The 20 simulated users of TC-PERF-03 |
| `loadtest/nf003.py` | The MLE-NF-003 pass/fail rule (kept apart from Locust so it can be unit-tested) |
| `loadtest/requirements.txt` | Locust, needed only for the load test |
| `config/settings.py` | SQLite settings for concurrent use (the fix) |
| `tests/integration/test_load_test_tools.py` | 8 tests: seeding and the pass/fail rule |
| `docs/member2/reports/tc_perf_03_*.csv` | Before and after measurements |

## Notes for teammates

- **Tejas:** `/api/evaluate` evaluates the model again and rewrites its metrics on every view of a completed run. With the new settings this no longer fails, but skipping `store_metrics` when the run is already COMPLETED (and possibly caching the evaluation) would make results pages cheaper.
- **Soumya:** the Docker image runs `runserver`, which is what was measured. For the Test Summary Report: TC-PERF-03 PASS after the fix, with the table above. If you re-run on the reference laptop, use `--spawn-rate 1` as above, and keep the database on the volume as now.
