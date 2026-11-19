# Deviations from the SRS, SAD and Test Plan

Each item says what the document says, what the code does, why, and where it
is visible. Checked against `main` at `cc9579f` (19 Nov 2026). Items that need
a decision from the team are marked **open**.

## Design (SAD)

| # | SAD / Test Plan says | The code does | Why | Where |
|---|---|---|---|---|
| D1 | SAD 4.1: `User (role field)`; the role is a field of the user. | The role is stored in a separate `Profile` table, and `user.role` is a property that reads it. | Replacing Django's user model after migrations were already merged broke those migrations, so the role was added beside the user instead. The behaviour (one role per account, checked on every page) is unchanged. | `accounts/models.py`, `accounts/permissions.py` |
| D2 | SAD 4.3.2: `GET /api/runs/{id}/report?format=csv` exports a run. | `GET /api/runs/<id>/export` returns the CSV. | The route was named when US-26 was built. The feature exists and has its own tests. | `training/urls.py`, `training/views.py::export_run_csv` |
| D3 | SAD 4.3.2: `GET /api/runs/compare?ids=1,2`. | `POST /api/runs/compare` with the run ids in the body. | Same as D2. The audit middleware also reads the ids from the body. | `training/urls.py`, `training/views.py::compare_runs`, `audit/middleware.py` |
| D4 | SAD 4.3.2 lists `GET /api/runs/{id}` (one run) and `DELETE /api/runs/{id}` (delete own run and artifact). | No route for either is registered in `training/urls.py`. A run is opened through the results page `/runs/<id>/results/` and `GET /api/evaluate/<id>`. **Open:** confirm with Varnika and Vikas whether deleting a run was dropped on purpose. | Not found in the code; reason to be confirmed. | `training/urls.py`, `evaluation/page_urls.py` |
| D5 | Test Plan Appendix A, TC-AUTH-01 step 2: login opens the dashboard. | Login opens the Welcome page (`LOGIN_REDIRECT_URL = accounts:home`). | Observation O-5, left as it is for now. The test is kept as an expected failure so the difference stays visible. | `config/settings.py`, `tests/system/test_appendix_a.py` |
| D6 | SAD 3.6 and Test Plan: Python 3.11. | The Docker image uses Python 3.12 (`python:3.12-slim`). The tests also ran on 3.13 locally. | A current supported version. | `Dockerfile` |
| D7 | SAD 3.6: TLS 1.2+ terminated at a reverse proxy in front of Django. | The container starts Django's `runserver`; HTTPS is switched on with `WBMME_HTTPS=1` (Secure cookies) and a local TLS development server `run_https_dev.py` (US-33). There is no reverse proxy in `compose.yaml`. | Demo scope. The Secure-cookie and redirect behaviour are implemented and tested. | `Dockerfile`, `compose.yaml`, `run_https_dev.py` |
| D8 | SAD 3.4 / epic mapping uses WBMME-4 to WBMME-11. | The GitHub issues carry different epic labels, for example `WBMME-8 Core Platform & Security` and `WBMME-1 Data Workspace`, and the board's Parent and Sub-issue fields are empty. | The labels were created separately from the SAD numbering. Being re-organised by the repository owner. | GitHub issues and project board |

## Requirements and scope (SRS)

| # | Item | What happened | Where |
|---|---|---|---|
| R1 | US-42 "Download a prepared dataset" is not in the original SRS backlog. | Added in Sprint 2 after the US-31 usability test (tester 5 could not see or reuse the cleaned data). It implements MLE-F-005 as a download and protects it with MLE-SR-003. | issue #114, PR #115, `datasets/prepared_download.py` |
| R2 | The Datasets page had a Preprocess panel and the menu a Models page. | Both were confusing, so the panel and the menu link were removed (PR #113). Preparation is now done through the training form and the prepared-data download. The Models template file still exists in `templates/training/models.html` but is not linked from the menu. | `templates/datasets/workspace.html`, `templates/base.html` |
| R3 | Lockout rule (MLE-SR-007). | Implemented as 5 failed logins counted from the first failure inside a 10-minute window, then a 15-minute lock. A locked API login returns 429 `ACCOUNT_LOCKED`; wrong credentials return 401 `INVALID_CREDENTIALS`. | `accounts/throttle.py` |

## Quality and process

| # | Item | Status |
|---|---|---|
| Q1 | SAD 3.6 lists flake8 and SonarQube. | As of `cc9579f` CI runs pytest with coverage and Bandit; there is no flake8 step. The SonarCloud setup is being done by the repository owner. A flake8 run over the app code (120 character lines) found 57 findings, mostly unused imports and blank-line style, not logic errors. |
| Q2 | Test Plan target: 70% coverage for service modules. | Measured 98% line and branch combined, see `docs/testing-reports/`. |
| Q3 | Defect D-1: a test share of 0.151 is rounded to 15% and accepted. | Known, not fixed; shown as an expected failure in the unit tests. |
| Q4 | `test_tc_sec_01` timed out once under coverage tracing. | Passes alone; recorded in the system validation report. |
| Q5 | `requirements.txt` pins only Django (`Django==5.2.18`); the other packages are unpinned, while US-14 asks for pinned requirements. | **Open.** CI runs against the newest pandas, which found a real bug in US-42 (fixed in PR #115). Pinning would make CI repeatable but hide that kind of bug. |
| Q6 | The author e-mail on some of Vikas's commits is wrong. | A `.mailmap` fixes it for git tools (PR #117); GitHub's contributor statistics do not use it. |
