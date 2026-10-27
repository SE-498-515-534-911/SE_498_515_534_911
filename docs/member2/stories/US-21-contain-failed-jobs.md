# US-21: Contain failed jobs

| | |
| --- | --- |
| Epic | WBMME-2 Model Training & Selection |
| Requirement | MLE-NF-006 (with the time-out of MLE-SR-006(d)) |
| Points / sprint | 5 / Sprint 2 |
| Owner | Varnika (Member 2) |
| SAD reference | 3.1.3 trade-offs, 3.7 R1, 4.4.1 fail safe, 4.4.2 `TRAINING_TIMEOUT`, 4.4.3 failure handling and restart recovery |
| Test Plan | Section 5: reliability testing by fault injection and a server restart |

**Story.** As a user I want a training job that fails to affect only that job, so that one bad run cannot stop the site or other people's work, and nothing I saved is lost when the server restarts.

## Acceptance criteria (SRS MLE-NF-006, SAD 4.4.3)

- [x] Training runs in a separate process, so a crash, a kill (for example out of memory) or a hang fails only that run.
- [x] A job is stopped at the time limit (`TRAINING_TIMEOUT_SECONDS`, default 300 s); the run is FAILED with code `TRAINING_TIMEOUT` and "Training took too long. Try a smaller dataset or a simpler model."
- [x] Any other failure sets the run to FAILED with code `TRAINING_FAILED` and a plain message; technical detail goes to the server log only.
- [x] No partial model is stored: the worker writes into a scratch folder that is always deleted; only a successful model is signed and moved into the user's folder.
- [x] Other users can keep using the site while a job fails or hangs, and the next job works normally.
- [x] Users, datasets and runs saved before a restart are present after it.
- [x] At start-up, runs still QUEUED or RUNNING are set to FAILED with "Training was interrupted by a server restart. Please start it again."
- [x] Evaluation (US-22) still receives TRAINED runs exactly as before.

## How it works

```
POST /api/train -> Run QUEUED -> server thread (jobs.execute_run) -> RUNNING
    runner.run(): new Python process ("spawn") runs worker.run_job()
        worker trains, writes model.joblib + result.json in MODEL_ARTIFACT_ROOT/_work/run_<id>_<x>/
    thread waits with the time limit, writing Run.heartbeat_at every 5 s
success: model signed and moved into the user's folder (artifacts.save_artifact_file) -> TRAINED
failure: run FAILED with code and message
always:  scratch folder deleted
```

Restart recovery (`training/recovery.py`):
- `python manage.py recover_runs --all` at start-up fails every QUEUED or RUNNING run (SAD 4.4.3). Put it in the Docker start command before the server starts.
- Without it, the first request after a start, and then one request every 30 s, fails runs whose heartbeat stopped 60 s ago. This covers `runserver` and is safe with several server processes, because a live job keeps beating.

## Files

| File | Purpose |
| --- | --- |
| `training/worker.py` | Runs inside the job process; trains, writes the model and `result.json`; never raises |
| `training/runner.py` | Starts the process, waits with the time limit, sends heartbeats, turns every outcome into a model path or `JobFailed(code, message)` |
| `training/jobs.py` | Status changes, scratch folder, signed hand-over, clean-up |
| `training/recovery.py`, `management/commands/recover_runs.py`, `apps.py` | Restart recovery |
| `training/artifacts.py` | New `save_artifact_file()`: signs a worker's model file in chunks and moves it in; existing functions unchanged |
| `experiments/models.py`, `migrations/0003_run_error_code_heartbeat.py` | `Run.error_code`, `Run.heartbeat_at` |
| `training/views.py` | Status shows the stored error code |
| `conftest.py` | Tests run workers in-process for speed; the fault-injection tests use real processes |
| `training/tests/faults.py`, `test_containment.py`, `test_recovery.py` | 27 tests |

## Evidence

Automated, with real child processes (`training/tests/test_containment.py`):

| Injected fault | Result |
| --- | --- |
| Process killed with no result (exit 137) | FAILED, "Training stopped unexpectedly..." |
| Exception nothing catches | FAILED, same message |
| Half-written model, then crash | FAILED, nothing kept |
| `MemoryError` during training | FAILED, generic message; detail only in the log |
| Reports success without a model / unreadable result | FAILED |
| Never finishes (limit 2 s) | Killed, FAILED, `TRAINING_TIMEOUT` |
| Crash, then a normal job | Second job TRAINED |

After every fault: no model record, no model file, no scratch folder, no child process left.

Live, on `runserver` (fresh database):

| Scenario | Result |
| --- | --- |
| A. Job hangs, limit 8 s | FAILED `TRAINING_TIMEOUT` after 8.0 s; another user's 10 requests meanwhile all OK, slowest 52 ms; 0 processes left |
| B. Job killed like an out-of-memory kill | FAILED with the plain message; other user's requests OK; 0 processes left |
| C. Server killed while a job is RUNNING | Users / datasets / runs 2 / 1 / 3 before and after; `recover_runs --all` failed the run as interrupted and removed its scratch folder; login and a new job worked (TRAINED) |
| D. Evaluation of a run trained in a separate process | `/api/evaluate` → COMPLETED, metrics and confusion matrix returned |

No tracebacks in the server log. Full suite: 546 passed, 1 expected failure (D-1 from US-11).

## Notes for teammates

- **Soumya (US-32 Docker):** start the container with `python manage.py migrate && python manage.py recover_runs --all && <server>`, and keep `db.sqlite3`, `DATA_ROOT` and `MODEL_ARTIFACT_ROOT` on a Docker volume so data survives a restart (MLE-NF-006).
- **Tejas (US-22):** `/api/evaluate` shows `TRAINING_FAILED` for a timed-out run; using `run.error_code or 'TRAINING_FAILED'` in `evaluation/views.py` would show `TRAINING_TIMEOUT` as SAD 4.4.2 says.

## Limits

- There is no memory cap per job; an out-of-memory kill by the operating system is handled as an ordinary contained failure.
- Starting a process adds about 1–2 s per job (loading Python, pandas and scikit-learn). US-20 measures it within the 60 s target.
