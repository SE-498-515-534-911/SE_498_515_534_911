# US-19: Upload Speed Target — Benchmark Results

## Acceptance criteria
- Upload a valid CSV of up to 10 MB.
- Generate the profile within 5 seconds.
- Pass five consecutive runs on the reference machine.

## Test results

Test file: 10,485,630 bytes (10.00 MiB)

| Run | HTTP status | Duration | Result |
|---:|---:|---:|---|
| 1 | 201 | 3.292 s | PASS |
| 2 | 201 | 0.636 s | PASS |
| 3 | 201 | 0.578 s | PASS |
| 4 | 201 | 0.592 s | PASS |
| 5 | 201 | 0.583 s | PASS |

Successful runs within 5 seconds: 5/5.

## Regression tests
Command: `python -m pytest datasets/tests.py -q`

Result: 13 passed in 14.32 seconds.

## Conclusion
All five measured upload requests returned HTTP 201 within the 5-second target.
