# US-39: Request and job limits

| | |
| --- | --- |
| Epic | WBMME-8 Core Platform & Security |
| Requirement | MLE-SR-006 (a) to (d); objective MLE-SO-003 Availability |
| Points / sprint | 5 / Sprint 2 |
| Owner | Varnika (Member 2) |
| SAD reference | 3.9 STRIDE: Denial of service; 4.3.1 Limits; 4.4.2 `PAYLOAD_TOO_LARGE`, `RATE_LIMITED`; 4.4.3 Quota and time-out; OI-3 |
| Test Plan | SV-06 (section 5.1) |

**Story.** As the operator of WBMME I want limits on request size, request rate and training jobs, so that one user or script cannot make the system unusable for everyone else.

## Acceptance criteria (SRS MLE-SR-006, Test Plan SV-06)

- [x] (a) A request body over 10 MB is refused with 413 `PAYLOAD_TOO_LARGE`, before the body is read. A CSV file of exactly 10 MB (accepted by SRS Table 4.2-1) still uploads.
- [x] (b) At most 120 requests in any 60 seconds per logged-in user, and per IP address when anonymous; the 121st gets 429 `RATE_LIMITED` with a `Retry-After` header. Static files are not counted.
- [x] (c) At most 2 QUEUED or RUNNING training jobs per user (1 for a Student). A further `POST /api/train` gets 429 `RATE_LIMITED` with a message that states the limit. The slot is free again once a job is TRAINED, COMPLETED or FAILED.
- [x] (d) A job running longer than 300 s is stopped and FAILED with `TRAINING_TIMEOUT` (built in US-21).
- [x] The server keeps answering other users while any limit is hit.

## How it works

| Part | Where | How |
| --- | --- | --- |
| (a), (b) | `training/middleware.py` (`RequestLimitsMiddleware`, after `AuthenticationMiddleware` in `config/settings.py`) | Checks every request except static files. `/api/` paths get the standard JSON envelope; pages get a short plain-text answer. |
| (a) | `training/limits.py` `body_too_large` | Compares the declared `Content-Length` with 10 MB. Multipart uploads get a 64 KB allowance for the form envelope, so a 10 MB file reaches the upload validator, which checks the file itself. |
| (b) | `training/limits.py` `hit` | Sliding window: the times of the last requests are kept per user (or IP) in Django's cache; a request is refused when 120 fall within the last 60 s. A burst cannot slip through across a minute boundary. |
| (c) | `training/views.py` `start_training`, `training/limits.py` `job_limit` | Counts the caller's QUEUED/RUNNING runs after the request is validated; checked again together with creating the run, so two requests at the same moment cannot both pass. |

Settings (all optional): `MAX_REQUEST_BYTES` (10 MB), `RATE_LIMIT_PER_MINUTE` (120), `TRAINING_JOB_LIMITS` (`{"STUDENT": 1, "DATA_SCIENTIST": 2}`), `TRAINING_TIMEOUT_SECONDS` (300).

## Files

| File | Purpose |
| --- | --- |
| `training/limits.py` | The limits and their settings |
| `training/middleware.py` | Request size and rate limits for every request |
| `config/settings.py` | One middleware line |
| `training/views.py` | Job quota in `POST /api/train` |
| `conftest.py` | Each test starts with empty request counters |
| `training/tests/test_limits.py` | 24 tests |

## Evidence: SV-06 on a live server

Run on `runserver` with jobs made to hang and the time limit lowered to 15 s (as SV-06 allows), while a separate user kept requesting a page every second.

| SV-06 step | Pass criterion | Result |
| --- | --- | --- |
| Send an 11 MB body | HTTP 413 | 413 |
| Send 130 requests in one minute as one user | 429 after the 120th | 120 × 200, then 429 from request #121 |
| Second job as a Student | Refused with a message | 429, "You already have 1 training job in progress, the limit for a Student. Wait for one to finish, then try again." |
| Third job as a Data Scientist | Refused with a message | 202, 202, then 429 with the Data Scientist message |
| Job longer than the limit | Failed with reason time-out | FAILED, `TRAINING_TIMEOUT`; the Student could start a new job afterwards |
| Throughout | Server answers other users | All 200, slowest 59 ms |

No tracebacks in the server log. Automated: 570 passed, 1 expected failure (D-1 from US-11).

## Notes for teammates

- **Soumya (US-32 Docker):** the request counters live in Django's cache. With the default in-memory cache they count per server process, so run one process (threads are fine), or configure a shared cache (for example Redis) if you run several processes; otherwise each process allows 120 requests. Behind a reverse proxy, anonymous requests all come from the proxy's address, so they share one per-IP limit; logged-in users are limited by account and are not affected.
- **US-30 load test:** use a separate account per simulated user, as TC-PERF-03 says (20 accounts); one account shared by all users would hit the per-user limit.
- **Frontend:** a 429 answer carries `Retry-After` (seconds); the job-limit message can be shown as it is.
