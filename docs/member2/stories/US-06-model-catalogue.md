# US-06: Model catalogue

| | |
| --- | --- |
| Epic | WBMME-2 Model Training & Selection |
| Requirement | MLE-F-007 (SRS 4.3.3, Table 4.3-1) |
| Points / sprint | 3 / Sprint 1 |
| Owner | Varnika (Member 2) |
| SAD reference | 4.3.2 endpoint summary, 4.3.4 `GET /api/models`, 4.4.2 error catalogue; DS-Model-01 |
| Test Plan | TC-MODEL-01 |

**Story.** As a Data Scientist or Student I want to choose a model from a fixed catalogue so that I can compare algorithms without writing code.

## Acceptance criteria

- [x] The catalogue has exactly four classification models: Logistic Regression, k-Nearest Neighbours, Decision Tree, Random Forest.
- [x] Each model exposes its default hyperparameters and permitted ranges, exactly as in SRS Table 4.3-1.
- [x] The catalogue is fixed: models are chosen by key from this list only; no user-supplied model or algorithm is accepted (MLE-SR-004, SAD risk R3).
- [x] `GET /api/models` returns the catalogue to a logged-in Data Scientist or Student (200).
- [x] Anyone not logged in gets 401 `AUTH_REQUIRED`; an Admin gets 403 `FORBIDDEN`; any method other than GET gets 405. All errors use the standard envelope of SAD 4.3.1.

## Files

| File | Purpose |
| --- | --- |
| `training/catalogue.py` | `ModelSpec`, `ParamSpec`, the four models, `get_model()`, `build_estimator()` |
| `training/views.py` | `list_models` view for `GET /api/models` |
| `training/urls.py` | Training API routes, mounted at `/api/` |
| `config/urls.py` | One line added: `path('api/', include('training.urls'))` |
| `training/tests/conftest.py` | Added `student`, `scientist`, `admin_user` fixtures (existing fixtures kept) |
| `training/tests/test_catalogue.py` | 20 tests of the catalogue against Table 4.3-1 |
| `training/tests/test_api_models.py` | 8 tests of the endpoint: roles, error envelope, payload, methods |

## Example response (shortened)

```json
{ "models": [
  { "key": "random_forest", "label": "Random Forest",
    "description": "Many decision trees voting together. ...",
    "defaults": { "n_estimators": 100, "max_depth": null },
    "params": [
      { "name": "n_estimators", "label": "Number of trees", "kind": "int",
        "default": 100, "minimum": 10, "maximum": 200, "choices": [],
        "range": "a whole number between 10 and 200" } ],
    "provides_feature_importance": true } ] }
```

## How to run

```bash
python manage.py migrate
python manage.py runserver
```
Log in as a Student or Data Scientist in the browser, then open `http://127.0.0.1:8000/api/models`.

## Test

