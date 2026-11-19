# Member 3 (Tejas Ponnappa): story to code map

Each row says where the code for a story lives, where its tests are, and which
issue and pull request delivered it. Paths are from the repository root.
Story points: Sprint 1 = 18, Sprint 2 = 27, total 45.

| Story | Issue / PR | Pts | What it does in plain words | Code | Tests |
|---|---|---|---|---|---|
| US-15 Register and log in (MLE-F-001, SR-001, SR-007) | #43 / #62, #67 | 5 | Visitors register with a username, e-mail and strong password, log in and out. Wrong passwords are refused, and 5 failures in 10 minutes lock the account for 15 minutes. | `accounts/validators.py` (`validate_username_format`, `validate_password_strength`); `accounts/forms.py` (`RegistrationForm`, `ApiRegistrationForm`, `LoginForm`); `accounts/throttle.py` (`is_locked`, `record_failure`, `clear_failures`); `accounts/api.py` (`register`, `login_view`, `logout_view`); `accounts/api_errors.py` (error envelope, `csrf_failure`); `accounts/models.py` (`LoginThrottle`); session and CSRF settings in `config/settings.py` | `accounts/tests/test_validators.py`, `test_forms.py`, `test_throttle.py`, `test_api_auth.py`, `test_session_security.py`, `test_views.py` |
| US-17 Role-based access (MLE-F-002) | #45 / #64, #67 | 5 | Every account has one role (Student, Data Scientist, Admin). Each page and endpoint checks the role and refuses everyone else with 403. | `accounts/models.py` (`Role`, `Profile`, `user.role`); `accounts/permissions.py` (`get_role`, `role_required`, `RoleRequiredMixin`); `accounts/middleware.py` (`AdminRoleMiddleware`: only an Admin may open Django `/admin/`) | `accounts/tests/test_roles.py`, `test_permission_helpers.py`, `test_access_control.py`, `test_role_migration.py` |
| US-09 Safe model artifacts (MLE-SR-004) | #20 / #65 | 3 | Only model files the system wrote itself, signed with HMAC-SHA256 and recorded in the database, can be loaded. A tampered or foreign file is never loaded. | `training/artifacts.py` (`save_artifact`, `save_artifact_file`, `load_artifact`, `_signature`, `_resolve_path`, `user_artifact_dir`); `training/models.py` (`ModelArtifact`) | `training/tests/test_artifacts.py`; `tests/integration/test_pipeline_stages.py::test_a_tampered_model_file_is_never_loaded_by_evaluation` |
| US-10 Evaluation metrics (MLE-F-010) | #23 / #66 | 5 | Accuracy, precision, recall, F1 and ROC-AUC on the test split, macro-averaged for 3 or more classes. Runs move from TRAINED to COMPLETED. | `evaluation/metrics.py` (`compute_metrics`); `evaluation/run_evaluation.py` (`evaluate_run`, `store_metrics`, `evaluate_and_complete`); `evaluation/services.py`; `evaluation/views.py` (`evaluate`) at `/api/evaluate/<run_id>`; `experiments/models.py` (`Metric`) | `evaluation/tests/test_metrics.py`, `test_run_evaluation.py`, `test_services.py`, `test_api_evaluate.py` |
| US-22 Confusion matrix and metric chart (MLE-F-011) | #24 / #86 | 5 | The run results page shows a confusion matrix whose counts add up to the number of test rows, and a bar chart of the metrics. | `evaluation/confusion.py` (`build_confusion_matrix`); `evaluation/views.py` (`results_page`) at `/runs/<run_id>/results/`; `templates/evaluation/results.html`; `static/wbmme/results.js`, `results.css`; Chart.js in `static/wbmme/vendor/` | `evaluation/tests/test_confusion.py`, `test_results_page.py` |
| US-23 Feature importance (MLE-F-012) | #25 / #88 | 3 | Features ranked by importance for Logistic Regression, Decision Tree and Random Forest; other models show a clear "not available" message. | `evaluation/importance.py` (`feature_importance`, `FeatureImportance`: tree `feature_importances_`; Logistic Regression mean absolute coefficient, normalised); shown on the results page | `evaluation/tests/test_importance.py` |
| US-37 Admin console (MLE-F-016) | #47 / #100 | 8 | An Admin lists users, changes roles, deactivates or reactivates accounts, lists and deletes datasets, and reads the audit log. Everyone else gets 403. | API: `accounts/admin_api.py` (`list_users`, `update_user`, `list_datasets`, `delete_dataset`, `list_audit`, `refuse_unless_admin`); `accounts/admin_services.py` (`remove_dataset`); routes in `accounts/admin_urls.py` under `/api/admin/`. Page: `accounts/views.py` (`admin_dashboard`) at `/accounts/admin-dashboard/`, `templates/accounts/admin_dashboard.html`, `static/wbmme/admin_console.js`, `admin_console.css` | `accounts/tests/test_admin_api_basics.py`, `test_admin_api_users.py`, `test_admin_api_user_update.py`, `test_admin_api_datasets.py`, `test_admin_api_audit.py`, `test_admin_panel_page.py` |
| US-38 Ownership checks and audit log (MLE-SR-005) | #48 / #99, #112 | 5 | Users see only their own datasets, runs and models (another user's item gives the same 404 as a missing one). Logins, uploads, trainings, exports, denied access and admin actions are written to the audit log with user, IP and time. | `audit/models.py` (`AuditLog`); `audit/services.py` (`record`, `client_ip`); `audit/signals.py` (login, logout, failed login, upload, training start); `audit/middleware.py` (`AuditMiddleware`: ACCESS_DENIED for 403 and other-user 404); one call in `training/jobs.py` (`_finish`) and one in `training/views.py` (`export_run_csv`); middleware order in `config/settings.py` | `audit/tests/test_record.py`, `test_auth_events.py`, `test_activity_events.py`, `test_access_denied.py`, `test_ownership.py`, `test_export_and_compare.py`, `test_admin_site.py` |
| US-31 Usability test | #34 / #116 | 3 | Five first-time users try to log in, upload, train and view metrics within 10 minutes; results and the issues found are recorded. | `docs/member3/stories/US-31-usability-test.md` (documentation only) | manual test |
| US-42 Download a prepared dataset (MLE-F-005; from US-31 tester feedback) | #114 / #115 | 3 | The owner downloads a cleaned copy of a dataset as CSV (missing values handled, categories encoded) without changing the original. Cells starting with `=`, `+`, `-` or `@` are neutralised, and each download is audited. | `datasets/prepared_download.py` (`download_prepared`, `prepare`, `neutralise_frame`, `safe_cell`); route `api/datasets/<id>/prepared` in `datasets/urls.py`; form in `templates/datasets/workspace.html` | `tests/test_us42_prepared_download.py` (48 tests) |

## Also delivered (not separate backlog stories)

* PR #113: UI fixes found while verifying, covered by `tests/test_ui_regressions.py`
  (37 tests): the Training page shows "done" for TRAINED runs, and the Preprocess
  panel and Models link were removed from the pages.
* PR #117 `.mailmap`, PR #118 README rewrite, PR #123 final testing reports.

## Quick answers to "where is X?"

| Question | Answer |
|---|---|
| Password rule | `accounts/validators.py::validate_password_strength` (at least 8 characters, a letter and a digit) |
| Lockout numbers (5 failures, 10 minutes, 15 minutes) | constants at the top of `accounts/throttle.py` |
| Role table (SRS Table 4.1-1) | `Role` and `Profile` in `accounts/models.py`, enforced in `accounts/permissions.py` |
| 30-minute session, HttpOnly, SameSite, CSRF | `SESSION_*` and `CSRF_*` in `config/settings.py` |
| JSON error shape and the 403 for a missing CSRF token | `accounts/api_errors.py` |
| Model file signature | `training/artifacts.py::_signature` (HMAC-SHA256 with `SECRET_KEY`) |
| Metric formulas | `evaluation/metrics.py::compute_metrics` (scikit-learn, macro average for 3 or more classes) |
| Audit event names | `audit/models.py` |
| CSV formula protection | `datasets/prepared_download.py::safe_cell` |
