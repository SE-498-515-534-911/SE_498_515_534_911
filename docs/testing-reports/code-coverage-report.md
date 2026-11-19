# Code coverage report (line coverage)

Tool: pytest-cov / coverage.py 7.x, run with branch tracing on. Packages
measured: `accounts`, `audit`, `datasets`, `training`, `evaluation`,
`experiments`, `config`. Test files and migrations are excluded.

| Statements | Missed | Line coverage |
|---|---|---|
| 2249 | 38 | **98.3%** (reported combined with branches as 98%) |

Test Plan target: at least 70% for service modules. **Met by a wide margin.**
63 files are at 100%.

## Files below 100% (line coverage)

| File | Stmts | Missed | Combined % | Lines not run |
|---|---|---|---|---|
| `accounts/admin_services.py` | 29 | 2 | 94% | 35-36 |
| `accounts/forms.py` | 61 | 0 | 97% | none (branch only) |
| `accounts/models.py` | 24 | 2 | 92% | 30, 59 |
| `accounts/views.py` | 31 | 1 | 95% | 15 |
| `audit/middleware.py` | 67 | 6 | 91% | 42, 46, 74-75, 107-108 |
| `audit/models.py` | 30 | 1 | 97% | 56 |
| `audit/signals.py` | 24 | 0 | 96% | none (branch only) |
| `datasets/errors.py` | 26 | 2 | 92% | 48-56 |
| `datasets/models.py` | 15 | 1 | 93% | 25 |
| `datasets/prepared_download.py` | 79 | 2 | 96% | 43, 87 |
| `datasets/views.py` | 65 | 1 | 98% | 170 |
| `evaluation/importance.py` | 37 | 2 | 91% | 60, 77 |
| `experiments/models.py` | 38 | 1 | 97% | 84 |
| `training/benchmarks/tc_perf_02.py` | 154 | 12 | 89% | 105-106, 114, 124, 144, 251-256, 260 |
| `training/limits.py` | 56 | 2 | 97% | 95, 99 |
| `training/models.py` | 9 | 1 | 89% | 19 |
| `training/runner.py` | 84 | 2 | 98% | 102-103 |
