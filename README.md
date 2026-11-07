# Web-Based ML Model Evaluator (WBMME)

A web application where a user uploads a CSV dataset, trains a classification model on it, and views the evaluation results (accuracy, precision, recall, F1, ROC-AUC, confusion matrix and feature importance). Every training run is saved. Admins manage accounts and dataset records and review an audit log.

Course project for **UE24CS341A – Software Engineering**, PES University (Jackfruit mini-project, 2026).

## Features

| Area | What it does |
|---|---|
| Accounts | Register as a Student or Data Scientist, log in and out. 5 failed logins within 10 minutes lock the account for 15 minutes; a session ends after 30 minutes of inactivity. |
| Datasets | Upload a CSV (up to 10 MB, 20 to 50,000 rows, 2 to 100 columns, 20 datasets per user), preview its first rows and column profile, **download a prepared copy** (missing values handled, text columns one-hot encoded), or press **Train** to continue with it. |
| Training | Choose a dataset, target column, one of 4 models (Logistic Regression, k-Nearest Neighbours, Decision Tree, Random Forest), its hyperparameters, how to handle missing values and the test share. Training runs as a background job. |
| Results | Metrics on the test and train splits, a bar chart, the confusion matrix and feature importance (Logistic Regression, Decision Tree and Random Forest). |
| Experiments | The history of your training runs, with a link to each run's results. |
| Admin | An Admin panel to list users, change a role, deactivate or reactivate an account, list and delete dataset records, and read the audit log. An Admin can never see what is inside a dataset. |

Two things are available through the API only, with no button yet: comparing 2 to 4 runs (`POST /api/runs/compare`) and exporting a run as CSV (`GET /api/runs/<id>/export`).

Safeguards: every user sees only their own datasets, runs and models; trained models are saved as signed files and only files the system wrote are ever loaded; at most 120 requests per minute per user; a training job is limited to 300 seconds, with 1 active job for a Student and 2 for a Data Scientist; CSV downloads neutralise spreadsheet formulas; important actions are written to an audit log.

## Roles

| Capability | Student | Data Scientist | Admin |
|---|---|---|---|
| Register | Yes | Yes | No (created by an Admin, or with `createsuperuser`) |
| Upload and view own datasets, train, view results | Yes | Yes | No |
| Active training jobs at one time | 1 | 2 | n/a |
| Manage users, list and delete dataset records, read the audit log | No | No | Yes |

## Technology

Python 3.11 or newer (CI uses 3.11, the Docker image 3.12), Django 5.2, pandas, scikit-learn, joblib, SQLite, Django templates with Chart.js (bundled in `static/wbmme/vendor`), Docker, GitHub Actions with pytest.

Architecture: layered, Django MVT, with a pipe-and-filter ML pipeline (Upload, Preprocess, Split, Train, Evaluate, Record), deployed as a single unit.

## Run it locally

Without Docker (see below for Docker):

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate        macOS and Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser     # this account gets the Admin role
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Other users register at `/accounts/register/` and choose Student or Data Scientist. The database (`db.sqlite3`) and the uploaded data (`private/`) stay in the project folder and are not committed.

To keep data somewhere else, set these environment variables before `migrate` and `runserver`:

| Variable | Meaning | Default |
|---|---|---|
| `DB_PATH` | SQLite database file | `db.sqlite3` |
| `DATA_ROOT` | Uploaded datasets | `private/datasets` |
| `MODEL_ARTIFACT_ROOT` | Trained model files | `private/model_artifacts` |
| `WBMME_HTTPS` | Set to `1` when serving over HTTPS, so session cookies are marked Secure | off |

## Using the app

1. **Log in.** The menu has Overview, Datasets, Training and Evaluation.
2. **Datasets:** upload a CSV. Use **Preview** to see its first rows and columns, **Download prepared CSV** for a cleaned copy, or **Train** to open Training with that dataset selected.
3. **Training:** pick the dataset, the target column and a model, adjust the parameters if you like, then **Start Training**. When it finishes, press **Training done: click to view results**.
4. **Results:** metrics for the test and train splits, the chart, the confusion matrix and feature importance (or a note when the model has none).
5. **Evaluation** (the Experiments page) lists all your runs; open any one to see its results.
6. **Admin:** after logging in as an Admin, open the **Admin panel** link on the home page (`/accounts/admin-dashboard/`).

Training runs and evaluation results belong to the logged-in user. A model catalogue page also exists at `/models/`, but it is not linked from the menu.

## API

All answers use the same JSON error format (SAD 4.3.1).

| Area | Endpoints |
|---|---|
| Authentication | `POST /api/auth/register`, `/api/auth/login`, `/api/auth/logout` |
| Datasets | `POST /api/upload`, `GET /api/datasets/<id>/prepared?strategy=median&keep=<column>`, `POST /api/datasets/preprocess` (preview only, no screen) |
| Models | `GET /api/models`, `POST /api/models/<key>/params/validate` |
| Training | `POST /api/train`, `GET /api/train/<run_id>` |
| Results | `GET /api/evaluate/<run_id>` |
| Runs | `GET /api/runs`, `GET /api/runs/<id>/export`, `POST /api/runs/compare` |
| Admin | `GET /api/admin/users`, `PATCH /api/admin/users/<id>`, `GET /api/admin/datasets`, `DELETE /api/admin/datasets/<id>`, `GET /api/admin/audit` |

## Tests and CI

```bash
python -m pytest --ignore=us01_datasets_code
```

This takes several minutes. `us01_datasets_code/` is the Sprint 1 prototype of the upload; the running app does not use it and pytest skips it.

GitHub Actions runs on every push and pull request: the tests with coverage and the Bandit security scan (`.github/workflows/tests.yml`), and an OWASP ZAP baseline scan of the Docker build (`.github/workflows/zap-baseline.yml`). Load tests with Locust are in `loadtest/`.

## Documents

| Document | File |
|---|---|
| Software Requirements Specification | `WBMME_SRS.pdf`; Part A: `individual files/Member1_SRS_PartA_Final.docx`, Part B: `individual files/Member2_SRS_PartB.docx` |
| Software Architecture Document (combined, v1.0) | `WBMME_SAD.pdf` |
| Test Plan (combined, v1.0) | `WBMME_TEST-PLAN.pdf` |
| Security validation | `security_validation.pdf` |
| Upload speed benchmark | `US19_BENCHMARK.md` |
| Story notes and reports | `docs/` (`docs/member2/stories`, `docs/member2/reports`, `docs/member3/stories`) |
| Usability test result | `docs/member3/stories/US-31-usability-test.md` |
| Individual contributions | `individual files/` (each member's own sections) |
| Diagrams used in the SAD | `diagrams/` |

## Repository layout

```
manage.py, requirements.txt, Dockerfile, compose.yaml, pytest.ini, conftest.py
config/        Django settings and the main URL list
accounts/      registration, login, roles, login lockout, the auth and admin APIs, the Admin panel
datasets/      CSV upload and validation, profiling, preprocessing, prepared-CSV download
training/      model catalogue, hyperparameters, background training jobs, limits, run history, compare and export
evaluation/    metrics, confusion matrix, feature importance, the results page and /api/evaluate
experiments/   the Run and Metric models and the Experiments page
audit/         the audit log (who did what, and when)
templates/     pages (Django templates)
static/        styles and scripts, including the bundled Chart.js
tests/         unit, integration and system tests (each app also has its own tests)
loadtest/      Locust load tests
docs/          story notes and reports
diagrams/, individual files/, WBMME_*.pdf    design documents
us01_datasets_code/    Sprint 1 prototype of the upload (not used by the app)
us-29_test files/      sample invalid CSV files for the upload security tests
run_https_dev.py       local HTTPS development server (it expects a certificate in your TEMP folder)
```

## Workflow

- `main` is the only long-lived branch and always holds the latest reviewed work. It is protected: changes go in by pull request with passing checks, and force-pushes and deletion are blocked.
- Each change is made on a short-lived branch, merged by pull request after review by the repository owner, and the branch is then deleted.
- Work items are tracked as GitHub issues in the linked GitHub Project (2 sprints, story points, epics).
- Commits are made under each member's own GitHub identity. Set `git config user.email` to an address verified on your GitHub account (or your GitHub no-reply address), or your commits will not be linked to your profile.

## Docker Setup

### Prerequisites

- Docker Desktop on Windows or macOS, or Docker Engine with the Docker Compose plugin on Linux.
- Git and the WBMME project files.

### Build and Run

From the project root directory, run:

```bash
docker compose up --build
```

This command builds the Docker image if required and starts the application. On startup, the container applies database migrations, runs the interrupted-training recovery command, and starts the Django development server.

Open the application in a browser:

`http://localhost:8000/`

### Stop the Application

Press `Ctrl + C` in the terminal running Docker Compose.

To start the application in the background, run:

```bash
docker compose up --build -d
```

To stop the background container, run:

```bash
docker compose down
```

### Persistent Storage

Docker Compose uses a named volume mounted at `/data` to preserve application data across container restarts and replacements.

- Database: `/data/db.sqlite3`
- Uploaded datasets: `/data/datasets`
- Model artifacts: `/data/model_artifacts`

The corresponding environment variables are `DB_PATH`, `DATA_ROOT`, and `MODEL_ARTIFACT_ROOT`.

The named volume is retained when `docker compose down` is run. Do not use `docker compose down -v` unless you intend to delete the persisted volume and its data.

### Development Server Note

The container runs Django's development server for development and demonstration purposes. It is not intended for production deployment without an appropriate production-ready server and deployment configuration.

## Sprints

| Sprint | Dates |
|---|---|
| Sprint 1 | 19 – 23 Oct 2026 |
| Sprint 2 | 26 – 30 Oct 2026 |

## Team

| Member | Name | GitHub | Main responsibility |
|---|---|---|---|
| 1 | Soumya (repository owner) | [KOTRASAISOUMYASRI](https://github.com/KOTRASAISOUMYASRI) | SRS Part A, Test Plan (1, 2, 6–9), planning, CI, Docker, UI building and integration, demo videos, final report|
| 2 | Varnika | [varnikasadineni](https://github.com/varnikasadineni) | SRS Part B, Test Plan (3, 4, 5, 13), model training, tests |
| 3 | Tejas Ponnappa | [TejasPonnappa](https://github.com/TejasPonnappa) | SAD architecture (3.3–3.9), Test Plan (10, 11, 12, 14, 15), evaluation, core platform and security, admin |
| 4 | Vikas | [vikasvittalaihole](https://github.com/vikasvittalaihole) | SAD design (cover, 1, 2, 3.1, 3.2, 4.1–4.6, 5), test cases and RTM design column, Data Workspace, run history, compare, export |
