# US-07: Set hyperparameters

| | |
| --- | --- |
| Epic | WBMME-2 Model Training & Selection |
| Requirement | MLE-F-008 (SRS 4.3.3, Table 4.3-1) |
| Points / sprint | 5 / Sprint 1 |
| Owner | Varnika (Member 2) |
| SAD reference | 4.3.4 parameter schema, 4.4.2 error catalogue; DS-Model-02 |
| Test Plan | TC-MODEL-01 (step 3: C = -5 is refused) |

**Story.** As a Data Scientist or Student I want to edit a model's hyperparameters, and be told clearly when a value is not allowed, so that I can tune a model without breaking it.

## Acceptance criteria

- [x] At least two hyperparameters per model are editable (every catalogue model has two).
- [x] A value outside its range, of the wrong type, or for an unknown setting is refused before training starts.
- [x] The message names the parameter and its permitted range, for example `C must be a number between 0.01 and 100.`
- [x] Boundary values are accepted (C = 0.01 and C = 100) and values just outside are refused (C = 0.009 and C = 100.01).
- [x] Settings left out take the catalogue default.
- [x] All problems are reported together in one response, not one at a time.
- [x] Only a logged-in Data Scientist or Student can use it (401 / 403 otherwise).

## Files

| File | Purpose |
| --- | --- |
| `training/params.py` | `validate_params(model_key, raw)` returns the complete clean parameter set and a list of `ParamError` |
| `training/views.py` | `validate_model_params` view; method/login/role checks shared with `list_models` |
| `training/urls.py` | `POST /api/models/<key>/params/validate` |
| `training/tests/test_params.py` | 23 tests: defaults, boundaries, wrong types, unknown settings, messages |
| `training/tests/test_api_params.py` | 13 tests of the endpoint: roles, error envelope, defaults, bad bodies |

## API

```
POST /api/models/logistic_regression/params/validate
{"params": {"C": 2.5}}

200 {"valid": true, "model": "logistic_regression", "params": {"C": 2.5, "max_iter": 200}}
```

```
POST /api/models/logistic_regression/params/validate
{"params": {"C": -5}}

400 {"error": {"code": "VALIDATION_ERROR",
               "message": "C must be a number between 0.01 and 100.",
               "details": {"field": "params.C",
                           "errors": [{"field": "params.C",
                                       "message": "C must be a number between 0.01 and 100."}]},
               "request_id": "..."}}
```

| Case | Status | Code |
| --- | --- | --- |
| Valid parameters (or none) | 200 | |
| Value out of range, wrong type, unknown setting | 400 | `VALIDATION_ERROR` |
| Body is not a JSON object | 400 | `VALIDATION_ERROR` |
| Model key not in the catalogue | 404 | `NOT_FOUND` |
| Not logged in / Admin | 401 / 403 | `AUTH_REQUIRED` / `FORBIDDEN` |
| Not POST | 405 | `METHOD_NOT_ALLOWED` |

## Deviation from the SAD

SAD 4.3.2 lists no separate validation endpoint; parameters are checked inside `POST /api/train`. This story adds `POST /api/models/<key>/params/validate` so the Select Model form can check values before the user presses Train, and so MLE-F-008 can be tested before US-08 exists. `POST /api/train` (US-08) calls the same `validate_params`, so the rule is defined once and cannot be bypassed.

## How to run

```bash
python manage.py migrate
python manage.py runserver
```
Log in as a Student or Data Scientist, then POST JSON to the URL above with the `X-CSRFToken` header (or run the tests).

## Test

```bash
python -m pytest training --cov=training --cov-branch
```
