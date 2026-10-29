# Web-Based ML Model Evaluator (WBMME)

A web application where a user uploads a CSV dataset, selects a machine-learning model, trains it, and views evaluation results (accuracy, precision, recall, F1, confusion matrix). Users can save and compare runs and export reports.

Course project for **UE24CS341A – Software Engineering**, PES University (Jackfruit mini-project, 2026).

## Team

| Member | Name | GitHub | Main responsibility |
|---|---|---|---|
| 1 | Soumya (repository owner) | [KOTRASAISOUMYASRI](https://github.com/KOTRASAISOUMYASRI) | SRS Part A, Test Plan (1, 2, 6–9), planning, CI, Docker, demo videos |
| 2 | Varnika | [varnikasadineni](https://github.com/varnikasadineni) | SRS Part B, Test Plan (3, 4, 5, 13), model training, tests |
| 3 | Tejas Ponnappa | [TejasPonnappa](https://github.com/TejasPonnappa) | SAD architecture (3.3–3.9), Test Plan (10, 11, 12, 14, 15), evaluation, core platform and security, admin |
| 4 | Vikas | [vikasvittalaihole](https://github.com/vikasvittalaihole) | SAD design (cover, 1, 2, 3.1, 3.2, 4.1–4.6, 5), test cases and RTM design column, Data Workspace, run history, compare, export |

## Technology

Python 3.11, Django 5, pandas, scikit-learn, joblib, SQLite (PostgreSQL optional), Django templates with Chart.js, Docker, GitHub Actions with pytest.

Architecture: layered, Django MVT, with a pipe-and-filter ML pipeline (Upload, Preprocess, Split, Train, Evaluate, Record), deployed as a single unit.

## Documents

| Document | File |
|---|---|
| Software Requirements Specification | Part A: `individual files/Member1_SRS_PartA_Final.docx`; Part B: `individual files/Member2_SRS_PartB.docx` |
| Software Architecture Document (combined, v1.0) | `WBMME_SAD.pdf` |
| Test Plan (combined, v1.0) | `WBMME_TEST-PLAN.pdf` |
| Individual contributions | `individual files/` (each member's own sections) |
| Diagrams used in the SAD | `diagrams/` |

## Repository layout

```
README.md
WBMME_SAD.pdf                 combined SAD
WBMME_TEST-PLAN.pdf           combined Test Plan
individual files/             each member's own documents
diagrams/                     component, ER, sequence, screen-map and wireframe images
```

Application code (Django project, tests, Dockerfile, CI workflow) is added in Sprint 1 and Sprint 2.

## Workflow

- `main` is the only long-lived branch and always holds the latest reviewed work.
- Each change is made on a short-lived branch, merged by pull request after review by the repository owner, and the branch is then deleted.
- Work items are tracked as GitHub issues in the linked GitHub Project (2 sprints, story points, epics).
- Commits are made under each member's own GitHub identity.

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