# Unit test report

Scope: the automated pytest tests that exercise one module or one Django view
at a time (validators, forms, throttle, permissions, metrics, confusion matrix,
feature importance, artifact store, audit, admin API, dataset services,
training services).

| Location | Tests collected |
|---|---|
| `accounts/` | 254 |
| `training/` | 270 |
| `audit/` | 109 |
| `evaluation/` | 92 |
| `datasets/` | 24 |
| `experiments/` | 6 |
| `tests/unit/` | 101 |
| `tests/test_us04_preprocessing.py` | 13 |
| `tests/test_us42_prepared_download.py` | 48 |
| `tests/test_ui_regressions.py` | 37 |
| `tests/test_ci.py` | 2 |
| **Total** | **956** |

Integration tests (`tests/integration/`, 19 tests: pipeline stages handing
over to each other, load-test tooling) and system tests (10 browser tests, see
the system validation report) make up the other 29 of the 985 collected.

## Result of the run

| Outcome | Count |
|---|---|
| Passed | 980 |
| Skipped | 1 |
| Expected failures (xfail) | 4 |
| Failed | 1 (`tests/system/test_appendix_a.py::test_tc_sec_01`, a browser system test, not a unit test) |

All unit and integration tests passed. Total run time was 25 min 39 s with
branch tracing switched on.

## Notes

* One unit test is an expected failure: D-1, a test share of 0.151 is accepted
  (see the system validation report).
