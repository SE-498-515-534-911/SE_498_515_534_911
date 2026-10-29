# US-20: Training speed target

| | |
| --- | --- |
| Epic | WBMME-2 Model Training & Selection |
| Requirement | MLE-NF-002 |
| Points / sprint | 3 / Sprint 2 |
| Owner | Varnika (Member 2) |
| SAD reference | 3.7 R1 (performance), 4.2.3 background job, 4.4.3 limits |
| Test Plan | TC-PERF-02 |

**Story.** As a Student I want training to finish quickly on a normal-sized dataset, so that I can try several models in one lab session.

## Requirement (SRS MLE-NF-002, TC-PERF-02)

Training any catalogue model with its default parameters on a dataset of up to 50,000 rows and 20 feature columns completes in 60 seconds or less, and the dashboard stays responsive while the job runs. TC-PERF-02 times each of the four models from start to Completed, on an uploaded generated data set, while the dashboard is loaded.

## Acceptance criteria

- [x] Each of the four models, with default settings, reaches COMPLETED (trained and evaluated) in 60 s or less on the 50,000-row, 20-feature test data set.
- [x] The dashboard keeps loading normally while the jobs run (every load 200, within 3 s, the page limit of MLE-NF-003).
- [x] The measurement is repeatable: a script runs TC-PERF-02 against any running server and prints PASS or FAIL.

## Defect found and fixed

The first measurement on `main` failed three of five checks:

| Check | Before (main, sparse features) | After (dense features) | Limit |
| --- | --- | --- | --- |
| Logistic regression, start → COMPLETED | 4.9 s | 3.8 s | 60 s |
| k-Nearest Neighbours | **no answer after 182 s** | 15.5 s | 60 s |
| Decision tree | 12.1 s | 4.7 s | 60 s |
| Random forest (100 trees, 1 core) | **71.2 s** | 18.5 s | 60 s |
| Dashboard while training: slowest load | **8.8 s** | 0.11 s | 3 s |

**Cause.** The preparation step (one-hot encoding inside the scikit-learn pipeline) produced a *sparse* matrix. Tree models train several times slower on sparse input (random forest: 61.7 s against 11.2 s for the training alone), and k-Nearest Neighbours computes distances on sparse data very slowly, which made its evaluation run for minutes and slowed the whole server, including the dashboard.

**Fix.** `training/pipeline.py` now produces dense features. Only a table whose prepared size would exceed 25 million cells (about 200 MB) falls back to sparse, to protect the server's memory (`MAX_DENSE_CELLS`). The benchmark data set needs about 2.2 million cells.

## How it is measured

`training/benchmarks/tc_perf_02.py` follows TC-PERF-02 step by step against a running server:
1. generates `generated_50k_rows_20_features.csv` (fixed seed; 15 numeric columns with 3 decimals, 3 of them with 5% missing values; 5 text columns with 8 values each; a 3-class target; 5.3 MB) and uploads it through `/api/upload`;
2. trains each model with default settings through `/api/train`;
3. records the time from the request to TRAINED and to COMPLETED (`/api/evaluate`);
4. meanwhile a second user loads the dashboard every second.

```bash
# start the server first: docker compose up   (or: python manage.py runserver)
python training/benchmarks/tc_perf_02.py --url http://127.0.0.1:8000 --json report.json
python training/benchmarks/tc_perf_02.py --write-csv generated_50k_rows_20_features.csv   # only the test data
```
Exit code 0 means every check passed.

## Result (after the fix)

Server: `runserver` with production settings (training in a separate process, US-21), 2-core Intel Xeon 2.1 GHz, 8 GB RAM, Linux, Python 3.13, scikit-learn 1.9, pandas 3.0.

| Model | To TRAINED | To COMPLETED | Test accuracy | Result |
| --- | --- | --- | --- | --- |
| Logistic regression | 3.3 s | 3.8 s | 0.782 | PASS |
| k-Nearest Neighbours | 3.2 s | 15.5 s | 0.606 | PASS |
| Decision tree | 4.2 s | 4.7 s | 0.686 | PASS |
| Random forest | 14.3 s | 18.5 s | 0.763 | PASS |
| Dashboard: 42 loads, 0 errors, average 0.018 s, slowest 0.114 s | | | | PASS |

Raw reports: `docs/member2/reports/tc_perf_02_before.json`, `tc_perf_02_after.json`. The server used here is a small 2-core machine, so the reference laptop should be at least as fast; re-run the script there (with Docker) for the final record.

## Files

| File | Purpose |
| --- | --- |
| `training/pipeline.py` | Dense features (`prepared_width`, `use_dense`, `MAX_DENSE_CELLS`) |
| `training/benchmarks/tc_perf_02.py` | The TC-PERF-02 script (standard library HTTP client, no new dependencies) |
| `training/tests/test_speed.py` | 13 fast tests: dense/sparse switch, test data, pass/fail rules, the script end to end on a small data set |
| `docs/member2/reports/tc_perf_02_*.json` | Before and after measurements |
| `accounts/tests/test_role_migration.py` | One-line test fix, see below |

## Also fixed: test isolation

`accounts/tests/test_role_migration.py` migrated the accounts app back and then forward only to `0002`, so `0003_login_throttle` was missing for every later test that uses the database for real transactions (pytest-django runs those last). The new end-to-end tests are the first such tests that log in, so they failed. The test now ends on the latest migrations, as its comment intended.

## Notes for teammates

- **Tejas (evaluation):** `/api/evaluate` evaluates a run inside the request. For k-Nearest Neighbours on 50,000 rows that request takes about 12 s (scoring both the 10,000 test rows and the 40,000 training rows). It is within the 60 s target, but a browser polling the Results page waits that long for one answer. Moving evaluation into the training job (status TRAINED → COMPLETED in the background) would keep every request short; worth considering for US-30 (pages within 3 s).
