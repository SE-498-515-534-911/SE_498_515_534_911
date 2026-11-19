# Final testing reports

Measured on `main` at commit `cc9579f` (after PR #122), 19 Nov 2026, in a fresh
virtual environment with Django 5.2.18, pandas 3.1.1, scikit-learn 1.9.1,
pytest 9.2.0 and pytest-cov 7.1.0.

| Report | File |
|---|---|
| Unit tests | [unit-test-report.md](unit-test-report.md) |
| System validation | [system-validation-report.md](system-validation-report.md) |
| Code coverage | [code-coverage-report.md](code-coverage-report.md) |
| Branch coverage | [branch-coverage-report.md](branch-coverage-report.md) |

## How the numbers were produced

```
pytest -q --ignore=us01_datasets_code \
  --cov=accounts --cov=audit --cov=datasets --cov=training \
  --cov=evaluation --cov=experiments --cov=config \
  --cov-branch --cov-config=<rc> --cov-report=term-missing:skip-covered
```

The coverage config omits test files, migrations, `us01_datasets_code`
(an early standalone prototype), `loadtest`, `manage.py`, `run_https_dev.py`
and the `wsgi`/`asgi` entry files, which contain no project logic.

Overall result: **985 tests collected: 980 passed, 1 skipped, 4 xfailed,
1 failed** (the failure is explained in the system validation report).
