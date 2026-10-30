# US-28: Integration and system tests

| | |
| --- | --- |
| Epic | WBMME-5 Testing & Validation |
| Requirement | Test Plan section 5 (Integration and System levels), Appendix A, section 13 |
| Points / sprint | 5 / Sprint 2 |
| Owner | Varnika (Member 2) |

**Story.** As the team I want the modules tested together and the Appendix A test cases executed end to end, so that we know the whole system works, not only each part.

## Acceptance criteria

- [x] Integration: the pipeline stages run in sequence through each app's real API (Upload → Preprocess → Train → Evaluate → Record), with the real database and file store, for every catalogue model.
- [x] Integration: failures stop at the right stage and are reported consistently by status, evaluation, history and the audit log.
- [x] System: every functional test case of Appendix A (TC-AUTH-01, TC-DATA-01, TC-DATA-02, TC-MODEL-01, TC-EVAL-01, TC-EXP-01, TC-SEC-01) runs end to end against a live server with production-like jobs.
- [x] System: the steps that depend on the browser run in a real browser.
- [x] Steps blocked by features not yet merged are written against the SAD contract and marked as expected failures, so they are tracked, not forgotten.
- [x] Actual results are recorded for Appendix A (`docs/member2/reports/appendix_a_execution.md`).
- [x] All tests run in CI on every pull request and are stable (three consecutive full runs, same result).

## Files

| File | Tests | Covers |
| --- | --- | --- |
| `tests/integration/test_pipeline_stages.py` | 11 | The chain for each of the 4 models with a scikit-learn oracle for the metrics; preprocessing choice end to end; two users in parallel; validation failure; corrupt file (422); job failure seen by every module; tampered model never loaded (MLE-SR-004); restart recovery seen by every module |
| `tests/system/test_appendix_a.py` | 7 (+3 expected failures) | One test per Appendix A test case, steps numbered as in the Test Plan |
| `tests/system/test_browser_flows.py` | 3 | Login and upload pages; wrong-password page; results page draws tiles, chart and confusion matrix (Chromium, Playwright) |
| `tests/support/` | | Test data sets named in Appendix A (generated, no binary files in the repo) and a small browser-like HTTP client |
| `tests/integration/conftest.py`, `tests/system/conftest.py` | | Fixtures: test client with jobs on commit; live server with a background thread and a separate training process; the Appendix A accounts |
| `training/middleware.py` | | Fix for defect D-2 (see below) |
| `docs/member2/reports/appendix_a_execution.md` | | Actual results for Appendix A |

## Defects found by these tests

| ID | Finding | Status |
| --- | --- | --- |
| D-2 | TC-DATA-02: an 11 MB file got 413 "The request is larger than 10 MB." instead of "The file is larger than 10 MB." The US-39 size limit answered before the upload validator. A file upload now gets the "file" message. | Fixed here (`training/middleware.py`, test in `training/tests/test_limits.py`) |
| O-5 | TC-AUTH-01 step 2: after login the browser goes to `/accounts/` (Welcome page), not the dashboard. | Reported to Tejas; pinned by a strict expected-failure test |

## Expected failures (`xfail(strict=True)`)

| Test | Waiting for |
| --- | --- |
| `test_tc_data_02_step_3_export_neutralises_formula_cells` | US-26 export (Vikas) |
| `test_tc_exp_01_compare` | US-25 compare (Vikas) |
| `test_tc_auth_01_step_2_login_lands_on_the_dashboard` | O-5 fix (Tejas) |

When the feature or fix lands, the test passes, and `strict=True` turns that into a failure, so whoever merges it removes the marker and the step counts as executed.

## How to run

```bash
python -m pytest tests/integration tests/system -v
# browser tests (skipped where Playwright is not installed, e.g. CI):
pip install playwright && python -m playwright install chromium
python -m pytest tests/system/test_browser_flows.py -v
```
