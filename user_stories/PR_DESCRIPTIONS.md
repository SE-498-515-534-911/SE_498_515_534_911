# Pull request descriptions (copy one into each PR)
Raise the pull requests **in this order**, one at a time. The branches are stacked (each contains the one before), so the repo owner should merge each PR before you open the next. After a merge, the next PR's diff shrinks to just its own story.
Title format used below: `US-xx: <story>`. Reviewer: the repo owner (Soumya).

---

## US-06  (branch `feature/us-06-model-catalogue`)

**Title:** `US-06: Fixed catalogue of 4 models with parameter ranges (Table 4`

### Summary
Fixed catalogue of 4 models with parameter ranges (Table 4.3-1) and GET /api/models.

### Requirement
MLE-F-007. Story write-up: `docs/member2/stories/US-06-model-catalogue.md`

### Testing
`python -m pytest -c member2_dev/pytest.ini` -> 23 tests; 1 commit.

### Notes for the reviewer
- Only new files are added (`training/`, `member2_dev/`, `loadtest/`, `docs/member2/`); no teammate's file is changed.
- Deviations from the SRS/SAD are listed in `docs/member2/DEVIATIONS.md`; how to plug into the team project is in `docs/member2/INTEGRATION.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016AqNySb7TZhbVjmWvUchag

---

## US-07  (branch `feature/us-07-hyperparameters`)

**Title:** `US-07: Hyperparameter validation with range messages, e`

### Summary
Hyperparameter validation with range messages, e.g. 'C must be a number between 0.01 and 100.'

### Requirement
MLE-F-008. Story write-up: `docs/member2/stories/US-07-hyperparameters.md`

### Testing
`python -m pytest -c member2_dev/pytest.ini` -> 52 tests (cumulative).

### Notes for the reviewer
- Only new files are added (`training/`, `member2_dev/`, `loadtest/`, `docs/member2/`); no teammate's file is changed.
- Deviations from the SRS/SAD are listed in `docs/member2/DEVIATIONS.md`; how to plug into the team project is in `docs/member2/INTEGRATION.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016AqNySb7TZhbVjmWvUchag

---

## US-08  (branch `feature/us-08-background-training`)

**Title:** `US-08: TrainingRun record, data pipeline, POST /api/train (202) and GET /api/`

### Summary
TrainingRun record, data pipeline, POST /api/train (202) and GET /api/train/<id>, per-user atomic model storage.

### Requirement
MLE-F-009. Story write-up: `docs/member2/stories/US-08-background-training.md`

### Testing
`python -m pytest -c member2_dev/pytest.ini` -> 95 tests (cumulative).

### Notes for the reviewer
- Only new files are added (`training/`, `member2_dev/`, `loadtest/`, `docs/member2/`); no teammate's file is changed.
- Deviations from the SRS/SAD are listed in `docs/member2/DEVIATIONS.md`; how to plug into the team project is in `docs/member2/INTEGRATION.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016AqNySb7TZhbVjmWvUchag

---

## US-11  (branch `feature/us-11-unit-tests`)

**Title:** `US-11: Unit tests of each core service; 100% coverage of training/; found and`

### Summary
Unit tests of each core service; 100% coverage of training/; found and fixed a NaN/Infinity test_size crash.

### Requirement
Test Plan 5. Story write-up: `docs/member2/stories/US-11-unit-tests.md`

### Testing
`python -m pytest -c member2_dev/pytest.ini` -> 139 tests (cumulative).

### Notes for the reviewer
- Only new files are added (`training/`, `member2_dev/`, `loadtest/`, `docs/member2/`); no teammate's file is changed.
- Deviations from the SRS/SAD are listed in `docs/member2/DEVIATIONS.md`; how to plug into the team project is in `docs/member2/INTEGRATION.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016AqNySb7TZhbVjmWvUchag

---

## US-20  (branch `feature/us-20-training-speed`)

**Title:** `US-20: 50,000x20 benchmark`

### Summary
50,000x20 benchmark. First run: random forest 67.6 s (limit 60 s). Fixed by dense features: now 12.9 s.

### Requirement
MLE-NF-002. Story write-up: `docs/member2/stories/US-20-training-speed.md`

### Testing
`python -m pytest -c member2_dev/pytest.ini` -> 145 tests incl. 3 perf.

### Notes for the reviewer
- Only new files are added (`training/`, `member2_dev/`, `loadtest/`, `docs/member2/`); no teammate's file is changed.
- Deviations from the SRS/SAD are listed in `docs/member2/DEVIATIONS.md`; how to plug into the team project is in `docs/member2/INTEGRATION.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016AqNySb7TZhbVjmWvUchag

---

## US-21  (branch `feature/us-21-contain-failed-jobs`)

**Title:** `US-21: Training in a separate process with time limit, scratch folder and res`

### Summary
Training in a separate process with time limit, scratch folder and result file; fault injection tests (crash, hang, exception, MemoryError, partial write).

### Requirement
MLE-NF-006. Story write-up: `docs/member2/stories/US-21-contain-failed-jobs.md`

### Testing
`python -m pytest -c member2_dev/pytest.ini` -> 158 tests (cumulative).

### Notes for the reviewer
- Only new files are added (`training/`, `member2_dev/`, `loadtest/`, `docs/member2/`); no teammate's file is changed.
- Deviations from the SRS/SAD are listed in `docs/member2/DEVIATIONS.md`; how to plug into the team project is in `docs/member2/INTEGRATION.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016AqNySb7TZhbVjmWvUchag

---

## US-39  (branch `feature/us-39-request-and-job-limits`)

**Title:** `US-39: Sliding-window rate limit (429), 10 MB body limit (413), job quota Stu`

### Summary
Sliding-window rate limit (429), 10 MB body limit (413), job quota Student 1 / Data Scientist 2, 300 s job time-out.

### Requirement
MLE-SR-006. Story write-up: `docs/member2/stories/US-39-request-and-job-limits.md`

### Testing
`python -m pytest -c member2_dev/pytest.ini` -> 191 tests (cumulative).

### Notes for the reviewer
- Only new files are added (`training/`, `member2_dev/`, `loadtest/`, `docs/member2/`); no teammate's file is changed.
- Deviations from the SRS/SAD are listed in `docs/member2/DEVIATIONS.md`; how to plug into the team project is in `docs/member2/INTEGRATION.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016AqNySb7TZhbVjmWvUchag

---

## US-28  (branch `feature/us-28-integration-system-tests`)

**Title:** `US-28: 6 integration tests (real child process) and 4 black-box system journe`

### Summary
6 integration tests (real child process) and 4 black-box system journeys.

### Requirement
Test Plan 13. Story write-up: `docs/member2/stories/US-28-integration-and-system-tests.md`

### Testing
`python -m pytest -c member2_dev/pytest.ini` -> 202 tests (cumulative).

### Notes for the reviewer
- Only new files are added (`training/`, `member2_dev/`, `loadtest/`, `docs/member2/`); no teammate's file is changed.
- Deviations from the SRS/SAD are listed in `docs/member2/DEVIATIONS.md`; how to plug into the team project is in `docs/member2/INTEGRATION.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016AqNySb7TZhbVjmWvUchag

---

## US-30  (branch `feature/us-30-load-test`)

**Title:** `US-30: Locust, 20 users, 90 s: 596 requests, avg 64 ms, p95 130 ms, 0 failure`

### Summary
Locust, 20 users, 90 s: 596 requests, avg 64 ms, p95 130 ms, 0 failures, 74 jobs completed.

### Requirement
MLE-NF-003. Story write-up: `docs/member2/stories/US-30-load-test.md`

### Testing
`python -m pytest -c member2_dev/pytest.ini` -> 202 tests; load test passed.

### Notes for the reviewer
- Only new files are added (`training/`, `member2_dev/`, `loadtest/`, `docs/member2/`); no teammate's file is changed.
- Deviations from the SRS/SAD are listed in `docs/member2/DEVIATIONS.md`; how to plug into the team project is in `docs/member2/INTEGRATION.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016AqNySb7TZhbVjmWvUchag
