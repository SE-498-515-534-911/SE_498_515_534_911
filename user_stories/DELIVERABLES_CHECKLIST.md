# Deliverables checklist (from the Part-1 and Part-2 sheets)

Legend: **Done** = finished and checked by me. **Yours** = needs you on GitHub or on camera. **Team** = belongs to a teammate; I can only see that I did not do it, so please confirm with them.

## Your 9 user stories (Sprint 1 and 2)

| Story | Points | Sprint | Status | Evidence |
| --- | --- | --- | --- | --- |
| US-06 Model catalogue | 3 | 1 | **Done** (code, tests, doc) | branch `feature/us-06-model-catalogue` |
| US-07 Set hyperparameters | 5 | 1 | **Done** | `feature/us-07-hyperparameters` |
| US-08 Train as a background job | 8 | 1 | **Done** | `feature/us-08-background-training` |
| US-11 Unit tests for core services | 5 | 1 | **Done**: 139 tests, 100% coverage | `feature/us-11-unit-tests` |
| US-20 Training speed target | 3 | 2 | **Done**: 12.9 s worst case vs 60 s | `feature/us-20-training-speed` |
| US-21 Contain failed jobs | 5 | 2 | **Done** | `feature/us-21-contain-failed-jobs` |
| US-39 Request and job limits | 5 | 2 | **Done** | `feature/us-39-request-and-job-limits` |
| US-28 Integration and system tests | 5 | 2 | **Done** | `feature/us-28-integration-system-tests` |
| US-30 Load test | 5 | 2 | **Done**: avg 64 ms, p95 130 ms, 0 failures | `feature/us-30-load-test` |

Total 44 points. 202 automated tests pass on Python 3.11 and 3.13 (97% coverage of `training/`).
Not yet true until you do it: **pushed to GitHub, PR raised by you, reviewed and merged by the owner** (see GITHUB_STEPS.md).

## Part-2 (sprints)

| Item | Status |
| --- | --- |
| 1. Backlog in a GitHub Project linked to the repo, story points, owners, two sprints | **Team/Yours**: the spreadsheet backlog exists; confirm the GitHub Project was created and your 9 cards are in it |
| 2b. GitHub Actions enabled | **Done for my part**: `.github/workflows/member2-tests.yml` (arrives with the last branch). **Team**: other members' workflows |
| 2c. Assigned member raises the PR | **Yours**: 9 PRs, text in PR_DESCRIPTIONS.md |
| 2d. Repo owner reviews and merges | **Team** (Soumya) |
| 2e. Using GPTs is allowed | **Yours**: be ready to explain every part. Viva notes are in your presentation doc; each story file in `docs/member2/stories/` has a "Notes for the viva" section |
| 2f. Follow the SRS, SAD, Test Plan | **Done**, deviations written in `docs/member2/DEVIATIONS.md` |
| 2g/h. 1-minute Sprint-1 video, uploaded to the repo | **Yours/Team** (due last week). Suggested content below |
| 2i. Deviations documented | **Done** (DEVIATIONS.md) |
| 3b. 2-minute Sprint-2 video | **Yours/Team** |
| 3c. Documentation complete | **Done for my part**: stories, INTEGRATION.md, DEVIATIONS.md, LOAD_TEST.md, reports. Final PDF versions: **Yours** |
| 3d. Freeze development | **Team**, after 30 Oct |

## Part-1 (documents)

| Item | Status |
| --- | --- |
| SRS (my part B: requirements, use case diagrams, security objectives and requirements) | **Done** earlier: `Member2_SRS_PartB.docx` |
| Test Plan core sections and test cases | **Done** earlier: `Member2_Test_Plan_Core.docx` |
| SRS parts A / intro (Soumya), SAD (Tejas) | **Team**: confirm they are submitted |
| Merging all parts into one PDF per document | **Team/Yours**: not done by me |

## Suggested content for a 60-second demo (my part has no screens)

1. (10 s) Show the repo and the 9 merged PRs / green Actions run.
2. (20 s) In a terminal run `python -m pytest -c member2_dev/pytest.ini`: 202 passed.
3. (20 s) Run `locust ...` headless (LOAD_TEST.md): "LOAD TEST PASSED, average 64 ms, 0 failures".
4. (10 s) Show one failed job (crash test) producing a friendly message while the next job still works.
Ask me if you want a ready-to-read script for the 2-minute video.

## Things I could not do
- Push to GitHub, open PRs, or create the GitHub Project (no GitHub access from this session).
- Verify teammates' stories or documents.
- Record the videos.
