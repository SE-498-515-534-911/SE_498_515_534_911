# US-11: Unit tests for core services

| | |
| --- | --- |
| Epic | WBMME-5 Testing & Validation |
| Requirement | Test Plan section 5 (unit level) and section 14 (coverage of 70% or more for service modules); supports MLE-F-002 to F-010, MLE-SR-003 |
| Points / sprint | 5 / Sprint 1 |
| Owner | Varnika (Member 2) |

**Story.** As a developer I want each core service tested on its own, so that a failure points at the broken service and not at the page in front of it.

## Acceptance criteria

- [x] Every service module named in Test Plan section 5 (validation, preprocessing, training, metrics, access checks) has unit tests.
- [x] Every service module reaches the section 14 target of 70% or more (all are now at 100% line and branch coverage).
- [x] Limits are tested with the Test Plan boundary values: file size 9.9, 10 and 10.1 MB; rows 19, 20, 50,000 and 50,001; columns 1, 2, 100 and 101; test share 10% and 50%.
- [x] Failure paths are tested, not only the happy path (nothing is stored after a refused or failed upload).
- [x] All tests run in GitHub Actions on every pull request; tests that existed but were never collected now run.
- [x] Tests need no network and leave no files behind (each gets its own temporary folder).
- [x] Defects found are reported to the owner and pinned by a test.

## What was done

1. **New unit tests** in `tests/unit/` (SAD Appendix B layout). No application code was changed.

| File | Tests | Covers |
| --- | --- | --- |
| `tests/unit/test_upload_validator_unit.py` | 39 | `datasets.validators`: file type, content type, size, encoding, header, columns, rows, CSV syntax |
| `tests/unit/test_dataset_services_unit.py` | 56 | `datasets.services`: profiling, storage and clean-up, 20-dataset limit, every preprocessing strategy, split rules |
| `tests/unit/test_metrics_and_access_unit.py` | 6 | `evaluation.metrics` ROC-AUC and input edge cases; `RoleRequiredMixin` for anonymous users |

The training services already have unit tests from US-06 to US-08 (`training/tests/`, 164 tests).

## How to run

```bash
python -m pytest --ignore=us01_datasets_code
python -m pytest --ignore=us01_datasets_code --cov=. --cov-branch --cov-report=term-missing
```
