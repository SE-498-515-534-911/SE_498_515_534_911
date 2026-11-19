# Branch coverage report

Tool: coverage.py with `--cov-branch` (every `if`, loop and `try` is checked
for both outcomes).

| Branches | Partially covered | Combined line + branch coverage |
|---|---|---|
| 552 | 17 | **98%** |

"Partially covered" means a decision was exercised in one direction by the
tests but not the other. Those 17 are listed below with the line that jumps
(`from->to`, `exit` means the end of the function).

| File | Partial branches |
|---|---|
| `accounts/forms.py` | 58->63, 94->96 |
| `accounts/views.py` | 1 (line 15) |
| `audit/middleware.py` | 2 |
| `audit/signals.py` | 39->exit |
| `datasets/prepared_download.py` | 2 |
| `datasets/views.py` | 1 |
| `evaluation/importance.py` | 2 |
| `training/benchmarks/tc_perf_02.py` | 139->145 and 5 more |

Full per-line output is produced by the command in the README.
