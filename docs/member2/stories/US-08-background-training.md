# US-08: Train as a background job

| | |
| --- | --- |
| Epic | WBMME-2 Model Training & Selection |
| Requirement | MLE-F-009 (with MLE-F-005, F-006 for the data steps) |
| Points / sprint | 8 / Sprint 1 |
| Owner | Varnika (Member 2) |
| SAD reference | 4.1.4 data model, 4.1.5 DD1–DD4, 4.2 Figure 6 steps 1–6, 4.3.4 `POST /api/train`, 4.4.2 errors; DS-Model-03 |
| Test Plan | TC-MODEL-01 |

**Story.** As a Data Scientist or Student I want training to run in the background, so that the page stays usable while a model trains and I can check its status.

## Acceptance criteria

- [x] `POST /api/train` takes the SAD request (dataset, target column, model, parameters, preprocessing, split) and returns `202 {"run_id", "status": "QUEUED", "links"}` without waiting for training.
- [x] The job runs in a background thread after the run is saved; the run moves QUEUED → RUNNING → TRAINED, or FAILED, with start and finish times.
- [x] The trained model is saved through the signed artifact store (US-09, `training.artifacts`) and linked to the run, so only the owner can load it.
- [x] Missing values, one-hot encoding and scaling are fitted on the training split only (no data leakage, SAD R4).
- [x] The split is stratified and repeatable for the same test size and seed (uses `datasets.services.split_dataset`, US-05).
- [x] Request problems are refused before a run is created: 400 `VALIDATION_ERROR` (bad body, parameter out of range, unknown model, bad option, test size, target column or target rule), 404 `NOT_FOUND` (dataset missing or someone else's), 422 `UNPROCESSABLE` (split cannot be stratified).
- [x] `GET /api/train/<run_id>` shows the status of the caller's own run; another user's run answers 404.
- [x] A failed run shows a plain message; internal errors are logged on the server and the user sees a generic message.
- [x] Admins cannot train (403).

## Files

| File | Purpose |
| --- | --- |
| `experiments/models.py`, `migrations/0001_initial.py` | `Run` (SAD 4.1.4): owner, dataset, target, model, params, preprocessing, split, status, error, artifact, times |
| `experiments/admin.py`, `apps.py` | Read-only Run admin; explicit `AutoField` |
| `training/schemas.py` | Validation of the request body |
| `training/pipeline.py` | Read, split (via US-05), preprocess and fit; `load_split` for evaluation |
| `training/jobs.py` | `submit` (after commit, in a thread) and `execute_run` |
| `training/views.py`, `urls.py` | `POST /api/train`, `GET /api/train/<run_id>` |
| `training/tests/conftest.py` | Dataset fixtures stored like the upload service stores them |
| `training/tests/test_pipeline.py`, `test_schemas.py`, `test_jobs.py`, `test_api_train.py` | 91 tests |

## API

```
POST /api/train
{"dataset_id": 7, "target_column": "survived", "model": "random_forest",
 "params": {"n_estimators": 100, "max_depth": 8},
 "preprocessing": {"missing": "median", "categorical": "one_hot"},
 "split": {"test_size": 0.2, "random_state": 42}}

202 {"run_id": 12, "status": "QUEUED",
     "links": {"status": "/api/train/12", "run": "/api/runs/12", "evaluate": "/api/evaluate/12"}}
```

`params`, `preprocessing` and `split` are optional; defaults are the catalogue defaults, `median` / `one_hot`, and `0.2` / `42`. `preprocessing.missing` is one of `median`, `mean`, `most_frequent`, `drop_rows`.

```
GET /api/train/12
200 {"run_id": 12, "status": "TRAINED", "dataset_id": 7, "target_column": "survived",
     "model": "random_forest", "params": {...}, "preprocessing": {...}, "split": {...},
     "created_at": "...Z", "started_at": "...Z", "finished_at": "...Z", "error": null}
```
A failed run has `"error": {"code": "TRAINING_FAILED", "message": "..."}`.

## For teammates

- **Evaluation (US-10, Tejas):** a run in status `TRAINED` is ready. Load the model with `training.artifacts.load_artifact(run.owner, run.artifact)` and rebuild the exact test split with `training.pipeline.load_split(run.dataset.file_path, run.target_column, run.preprocessing_json['missing'], run.split_json['test_size'], run.split_json['random_state'])`. Then set the run to `COMPLETED` (Figure 6, steps 7–10).
- **Run history (US-24, Vikas):** `experiments.Run` is the run table of SAD 4.1.4; filter by `owner`. Add `Metric` and the `/api/runs` endpoints there.
- **Front end:** send `X-CSRFToken` on POSTs and poll `GET /api/train/<run_id>` until the status is `TRAINED` or `FAILED`.

## Deviations from the SAD

| SAD | Here | Why |
| --- | --- | --- |
| Run has `artifact_path` | Run has `artifact`, a link to `training.ModelArtifact` | The signed artifact store (US-09) already records path and signature; a link keeps one source of truth (DD3). |
| Run columns in Figure 3 | Adds `target_column`, `split_json`, `created_at` | Needed to rebuild the test split (DD2: one record reproduces one run) and to list runs newest first. |
| Polling uses `GET /api/evaluate/{id}` | Adds `GET /api/train/{id}` (status only) | `/api/evaluate` arrives with US-10; this lets the status be shown now. `/api/evaluate` can replace it later. |
| File store `data/{user_id}/models/{run_id}.joblib` | `MODEL_ARTIFACT_ROOT/user_{id}/{uuid}.joblib` | Layout of the existing artifact store (US-09). |
| Rate and job limits (MLE-SR-006, 429) | Not yet | US-39 (Sprint 2). |
| Interrupted runs marked FAILED at start-up | Not yet | US-21 (Sprint 2). |

## How to run

```bash
python manage.py migrate
python manage.py runserver
```
Log in as a Student or Data Scientist, upload a CSV in the Data Workspace, then POST the JSON above to `/api/train` with the `X-CSRFToken` header and poll `/api/train/<run_id>`.

## Test

```bash
python -m pytest training --cov=training --cov=experiments --cov-branch
```
