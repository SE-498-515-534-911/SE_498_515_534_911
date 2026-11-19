# Architecture to code map

This maps each box of the SAD component diagram (section 3.3, descriptions in
3.4) and each sequence-diagram step (4.2) to the file that implements it.
Paths are from the repository root. Pattern: Django MVT with a pipe-and-filter
ML pipeline (SAD 3.5).

## Components (SAD 3.4)

| SAD component | Where the code is |
|---|---|
| Web UI | `templates/` (`base.html`, `dashboard.html`, `datasets/workspace.html`, `training/configuration.html`, `evaluation/results.html`, `experiments/list.html`, `accounts/*.html`) and `static/wbmme/` (`app.css`, `results.js`, `admin_console.js`; Chart.js in `static/wbmme/vendor/`). Page views: `datasets/views.py` (`dashboard`, `dataset_workspace`), `training/page_views.py`, `evaluation/views.py` (`results_page`), `experiments/views.py`, `accounts/views.py`. |
| API Gateway and Controllers | URL table `config/urls.py`, which includes `accounts/api_urls.py` (`/api/auth/`), `accounts/admin_urls.py` (`/api/admin/`), `training/urls.py` (`/api/models`, `/api/train`, `/api/runs`), `evaluation/urls.py` (`/api/evaluate/`), `datasets/urls.py` (`/api/upload`, `/api/datasets/...`). Controllers are the view functions those files point at. |
| Auth and Access Control | `accounts/`: `forms.py` and `validators.py` (registration rules), `api.py` and `views.py` (login, logout), `throttle.py` (lockout), `models.py` (`Role`, `Profile`, `LoginThrottle`), `permissions.py` (`role_required`, `RoleRequiredMixin`), `middleware.py` (`AdminRoleMiddleware`), `api_errors.py` (error envelope). Session and CSRF settings: `config/settings.py`. |
| Data Workspace | `datasets/`: `validators.py` (`validate_upload`), `services.py` (`profile_csv`, `upload_dataset`, `preprocess_dataframe`, `split_dataset`), `views.py` (`upload_view`, `preprocess_dataset`), `prepared_download.py` (`download_prepared`), `models.py`, `errors.py`. |
| Model Selection and Training | `training/`: `catalogue.py` (registry of the four models, `build_estimator`), `params.py` (`validate_params`), `pipeline.py` (`make_split`, `build_pipeline`, `train`), `jobs.py` (`submit`, `execute_run`), `runner.py` and `worker.py` (training in a separate process with a timeout), `recovery.py` (runs interrupted by a restart become FAILED), `artifacts.py` (signed model store), `views.py` (`list_models`, `start_training`, `training_status`). |
| Evaluation and Explainability | `evaluation/`: `metrics.py` (`compute_metrics`), `confusion.py`, `importance.py`, `run_evaluation.py` (`evaluate_and_complete`), `services.py`, `views.py` (`evaluate`). |
| Experiment Management and Reporting | `experiments/models.py` (`Run`, `Metric`), `training/views.py` (`run_history`, `export_run_csv`, `compare_runs`), `experiments/views.py` (history page). |
| Logging, Monitoring and Audit | `audit/`: `models.py` (`AuditLog`), `services.py` (`record`, `client_ip`), `signals.py`, `middleware.py`. |
| Input Validation and Security Controls | Upload checks `datasets/validators.py`; request size and rate limits `training/limits.py` and `training/middleware.py` (`RequestLimitsMiddleware`); CSRF `CsrfViewMiddleware` plus `accounts/api_errors.py`; safe model loading `training/artifacts.py`; CSV formula neutralisation `training/views.py` (`_safe_csv_cell`) and `datasets/prepared_download.py` (`safe_cell`). |
| Relational DB | SQLite, path from `DB_PATH` (`config/settings.py`); tables from the `models.py` of each app and their `migrations/`. |
| File Store | Datasets under `DATA_ROOT`, model files under `MODEL_ARTIFACT_ROOT`, both per user and outside the web root (`config/settings.py`). |

Middleware order (`config/settings.py`): Security, Session, Common, CSRF,
Authentication, `audit.middleware.AuditMiddleware`,
`accounts.middleware.AdminRoleMiddleware`,
`training.middleware.RequestLimitsMiddleware`, Messages, Clickjacking.

## Sequence diagrams (SAD 4.2)

| Step in the diagram | Code |
|---|---|
| 4.2.1 Login: CSRF check, then rate limit, then credentials | CSRF: `CsrfViewMiddleware`; lock check and credentials: `accounts/forms.py::LoginForm.clean` and `accounts/api.py::login_view`, using `accounts/throttle.py::is_locked` |
| Failure: same generic message, 429 when locked, audit entry | `accounts/api.py::login_view`; `audit/signals.py::log_failed_login` |
| Session cookie HttpOnly, Secure, role in the response | `SESSION_COOKIE_*` in `config/settings.py`; `accounts/api.py::_user_json` |
| 4.2.2 Upload: auth, role, CSRF, then validator before saving | `datasets/views.py::upload_view`, `datasets/validators.py::validate_upload`, `datasets/services.py::upload_dataset` |
| Saved under a generated name in the owner's directory, profile as JSON | `datasets/services.py::upload_dataset`, `profile_csv` |
| 4.2.3 `/api/train` returns 202 with a run id | `training/views.py::start_training` |
| Background job, split, fit on training split only, save artifact | `training/jobs.py::submit`, `training/pipeline.py::train`, `training/artifacts.py::save_artifact` |
| Evaluation and run record | `evaluation/run_evaluation.py::evaluate_and_complete`, `experiments/models.py` |
| Browser polls `/api/evaluate/{run_id}` | `evaluation/views.py::evaluate`; client side `static/wbmme/results.js` |

## API endpoints (SAD 4.3.2) and the real routes

| Purpose | Route in the code | Handler |
|---|---|---|
| Register, log in, log out | `POST /api/auth/register`, `/login`, `/logout` | `accounts/api.py` |
| Upload | `POST /api/upload` | `datasets/views.py::upload_view` |
| Model catalogue, parameter check | `GET /api/models`, `POST /api/models/<key>/params/validate` | `training/views.py` |
| Train and status | `POST /api/train`, `GET /api/train/<run_id>` | `training/views.py` |
| Evaluate | `GET /api/evaluate/<run_id>` | `evaluation/views.py::evaluate` |
| History, export, compare | `GET /api/runs`, `GET /api/runs/<id>/export`, `POST /api/runs/compare` | `training/views.py` |
| Admin | `/api/admin/users`, `/users/<id>`, `/datasets`, `/datasets/<id>`, `/audit` | `accounts/admin_api.py` |
| Prepared dataset download | `GET /api/datasets/<id>/prepared` | `datasets/prepared_download.py` |

The export and compare routes differ from the SAD text, see
[deviations.md](deviations.md).
