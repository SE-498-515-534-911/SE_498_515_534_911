# Test Plan Appendix A: execution record (Sprint 2)

Executed 30 Oct 2026 on `main` at `7bf9f2e` plus the US-28 branch, by the automated system tests in `tests/system/` (live server over HTTP, training in a background thread and a separate process, as deployed) and the browser tests in `tests/system/test_browser_flows.py` (Chromium). Each functional test case is one test; the step numbers are those of Appendix A.

Run: `python -m pytest tests/system -v` → 10 passed, 3 expected failures (steps blocked by features not yet merged, or an open observation). The whole suite (`python -m pytest --ignore=us01_datasets_code`) ran three times in a row with the same result: 702 passed, 4 expected failures.

| Test case | Step | Expected result (Appendix A) | Actual result | Test result |
| --- | --- | --- | --- | --- |
| TC-AUTH-01 | 1–2 | User reaches the dashboard; session cookie is HttpOnly | Login accepted (302), `sessionid` cookie has HttpOnly, dashboard opens. After login the browser is sent to `/accounts/` (a Welcome page), not the dashboard: observation O-5 | Pass, with O-5 |
| | 3 | Log out | Logged out; the dashboard then redirects to the login page | Pass |
| | 4 | Wrong password refused with a generic error, no session | Page shows the form error; API answers 401 "Invalid username or password."; no session cookie | Pass |
| | 5 | Stored password is a salted hash | Stored value starts with `pbkdf2_sha256$`; the password text is not in it | Pass |
| | 6 | Weak password refused with a message per field | 400 `VALIDATION_ERROR`, message for the `password` field | Pass |
| | 7 | Deactivated account cannot log in | 401. (Account deactivated directly; the Admin console for it is US-37, not merged) | Pass |
| TC-DATA-01 | 1–3 | File saved in the user's directory; preview; profile matches the file | 201; file in `DATA_ROOT/<user id>/datasets/`; 1,000 rows × 5 columns; names, types and missing counts equal the file's; 20-row preview; page shows "Uploaded sample_1000rows.csv — 1000 rows and 5 columns" | Pass |
| TC-DATA-02 | 1–2 | notes.txt 415; oversize_11MB 413 "The file is larger than 10 MB."; empty, no_header, short_19rows 400 naming the problem; exact_10MB accepted | All as expected. **Defect D-2 found and fixed:** oversize_11MB first answered "The request is larger than 10 MB." (US-39 size limit); now "The file is larger than 10 MB." | Pass (after fix) |
| | 3 | Formula cells neutralised in the export | Export (US-26) not merged; step written against SAD 4.3.6, expected failure | Blocked |
| | 4 | No rejected file stored | Only exact_10MB.csv is in the file store; one Dataset record | Pass |
| TC-MODEL-01 | 1–3 | Out-of-range C refused, message names parameter and range | C = 1.0 accepted; C = 101 refused: "C must be a number between 0.01 and 100." (validate endpoint and `/api/train`) | Pass |
| | 4 | Status Queued, Running, Completed; artifact for this user only; run in history | Seen: QUEUED → RUNNING → TRAINED → COMPLETED; artifact owned by student_test1; another user gets 404; run listed in history | Pass |
| | 5 | Student's second job refused, limit stated | 429: "You already have 1 training job in progress, the limit for a Student. Wait for one to finish, then try again." | Pass |
| TC-EVAL-01 | 1–3 | Results page; metrics; confusion matrix renders | Page opens; status Completed; metric tiles and chart drawn; 3 × 3 matrix totals 24 (20% of 120 rows); no JavaScript errors | Pass |
| | 4 | Metrics equal a scikit-learn reference within 0.001 (macro for >2 classes) | Accuracy, precision, recall, F1 equal the reference within 0.001; averaging "macro" | Pass |
| TC-EXP-01 | 1–2 | Both runs listed with dataset, model, parameters, metrics and time | Logistic Regression and Random Forest listed newest first, COMPLETED, with parameters, test metrics and times | Pass |
| | 3–4 | Compare side by side; mixed datasets refused | Compare (US-25) not merged; steps written against SAD 4.3.6, expected failure | Blocked |
| TC-SEC-01 | 1 | User B denied User A's dataset and run, no data returned | 404 for status, evaluate, results page, training on A's dataset and preprocessing it; no data values in any answer | Pass |
| | 2 | User B denied admin pages | 403 for `/admin/` and the admin dashboard | Pass |
| | 3 | Admin opens user management | Django admin user list opens for admin_test1 | Pass |
| | 4 | Audit log shows the denied attempts with user and time, no data | ACCESS_DENIED entries for student_test1 with timestamps, including `run:<id>`; no data values in the log | Pass |
| | 5 | Admin sees dataset metadata only, never contents | No route gives the Admin dataset contents (403/404 everywhere). Listing metadata is the Admin console (US-37, not merged) | Pass (contents part) |
| TC-PERF-01 | | Upload of 10 MB in 5 s, five times | See US-19 (`US19_BENCHMARK.md`): 5/5 within 5 s | Pass (US-19) |
| TC-PERF-02 | | Each model ≤ 60 s to Completed; dashboard responsive | See US-20 (`docs/member2/reports/tc_perf_02_after.json`): slowest 18.5 s; dashboard slowest load 0.11 s | Pass (US-20) |
| TC-PERF-03 | | Pages ≤ 3 s for 20 users | US-30 load test | To run (US-30) |

## Defects and observations from this execution

| ID | Severity | Finding | Status |
| --- | --- | --- | --- |
| D-2 | Low | 413 for an oversize file said "request" instead of "file" (US-39 middleware answered before the upload validator) | Fixed in this PR |
| O-5 | Low | After login the browser lands on `/accounts/` (Welcome page), TC-AUTH-01 step 2 expects the dashboard. `LOGIN_REDIRECT_URL = 'accounts:home'` in `config/settings.py`; pointing it at the dashboard would match the test case. Pinned by a strict expected-failure test | Open (owner: Tejas) |
| D-1 | Low | (from US-11) `split_dataset` accepts a test share of 0.151 | Open (owner: Vikas) |
