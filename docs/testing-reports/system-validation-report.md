# System validation report

Scope: end-to-end checks of the running application, one test per functional
case of Test Plan Appendix A (`tests/system/test_appendix_a.py`). The tests
start a live server on a real port and talk to it over real HTTP with a small
client (`tests/support/http.py`, class `Browser`), with training in a background
thread and a separate process as on the deployed system. This client is not a
real web browser, so it does not run the pages' JavaScript. The performance cases TC-PERF-01 to 03 are
run separately (US-19, US-20 and the US-30 load test).

| Test | Test Plan case | Result in the full run |
|---|---|---|
| `test_tc_auth_01` | TC-AUTH-01 login with valid and invalid credentials | Passed |
| `test_tc_auth_01_step_2_login_lands_on_the_dashboard` | TC-AUTH-01 step 2 | Expected failure, see below (O-5) |
| `test_tc_data_01` | TC-DATA-01 upload a valid CSV and view its profile | Passed |
| `test_tc_data_02` | TC-DATA-02 reject invalid or unsafe uploads | Passed |
| `test_tc_data_02_step_3_export_neutralises_formula_cells` | TC-DATA-02 step 3 | Expected failure, see below (API route) |
| `test_tc_model_01` | TC-MODEL-01 select a model, set parameters, train | Passed |
| `test_tc_eval_01` | TC-EVAL-01 metrics and confusion matrix | Passed |
| `test_tc_exp_01_history` | TC-EXP-01 save runs (steps 1-2) | Passed |
| `test_tc_exp_01_compare` | TC-EXP-01 compare runs (steps 3-4) | Expected failure, see below (API route) |
| `test_tc_sec_01` | TC-SEC-01 access control and data isolation | **Failed in the full run, passed when run alone** |

## Expected failures (xfail, marked `strict=True`)

These tests are kept red on purpose so the difference from the design is
visible. They are the deviations to explain at the demo.

1. **O-5, login landing page.** The Test Plan expects login to open the
   dashboard; the app opens the Welcome page (`LOGIN_REDIRECT_URL =
   accounts:home`).
2. **Report export route.** The test was written against the SAD contract
   `GET /api/runs/{id}/report?format=csv`. The implemented route is
   `GET /api/runs/{id}/export` (US-26, merged, with its own passing tests).
   The xfail reason in the test file ("not merged yet") is out of date; the
   feature exists under a different URL.
3. **Compare route.** The test was written against `GET
   /api/runs/compare?ids=a,b`. The implemented route is `POST
   /api/runs/compare` (US-25, merged, with its own passing tests). Same
   out-of-date reason text.
4. **D-1, test share 0.151** is rounded to 15% and accepted (unit test
   `test_share_that_is_not_a_whole_5_percent_step_is_refused`). This is a
   known defect, not yet fixed.

## The one failure

In the full run with coverage tracing on, `test_tc_sec_01` timed out waiting for
a training run to finish (`run 8 did not finish: ['RUNNING']`). Run alone,
without tracing, it passed (1 passed in 60 s). Branch tracing slows the
training thread, so we believe the test's wait limit is too tight under
tracing rather than the application being at fault. We did not change the
test; this is recorded as a known timing sensitivity.

## Other system-level evidence

* Integration tests: `tests/integration/` (19 tests, all passed).
* Security validation SV-01 to SV-10: `security_validation.pdf`; ZAP baseline
  scan in `.github/workflows/zap-baseline.yml`.
* Usability test: `docs/member3/stories/US-31-usability-test.md`.
* Load test: `loadtest/` and `US19_BENCHMARK.md`.

## Real-browser tests

`tests/system/test_browser_flows.py` (3 tests) drives a real Chromium browser
with Playwright, for the steps that depend on what the pages draw with
JavaScript: the login and upload pages (TC-AUTH-01 steps 1-2, TC-DATA-01) and
the results page with its metrics and confusion matrix (TC-EVAL-01 steps 1-3).

Playwright is not in `requirements.txt`, so these tests are skipped where it is
not installed. That was the case in CI and in the run reported here: the one
skipped test in the totals is this file. They were not executed in this run. To
run them:

```
pip install playwright pytest-playwright
python -m playwright install chromium
python -m pytest tests/system/test_browser_flows.py
```
