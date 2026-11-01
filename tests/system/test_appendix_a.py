"""US-28 system tests: the functional test cases of Test Plan Appendix A, executed end to end.

Each test is one test case; the step numbers and expected results are the ones
in Appendix A. They run against a live server over HTTP (see conftest.py).
Steps that need a feature not merged yet are written against the SAD contract
and marked ``xfail(strict=True)``: they turn red as soon as the feature lands,
so the marker can be removed and the step counts as executed.

The performance cases (TC-PERF-01 to 03) are run separately: US-19,
training/benchmarks/tc_perf_02.py (US-20) and the load test (US-30).
"""
from pathlib import Path

import pandas as pd
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from audit.models import Action, AuditLog
from datasets.models import Dataset
from experiments.models import Run
from training import pipeline
from training.artifacts import load_artifact
from training.models import ModelArtifact

from support.data import INVALID_FILES, csv_bytes, csv_of_exactly, iris_like, sample_1000rows

from .conftest import PASSWORD, wait_for

pytestmark = pytest.mark.django_db(transaction=True)
MB = 1024 * 1024


def upload_iris(b):
    response = b.upload('iris_like.csv', csv_bytes(iris_like()))
    assert response.status == 201, response.text
    return response.json()['dataset']['id']


def train(b, dataset_id, model='logistic_regression', **extra):
    return b.post_json('/api/train', {'dataset_id': dataset_id, 'target_column': 'species',
                                      'model': model, **extra})


def completed_run(b, dataset_id, model='logistic_regression', **extra):
    response = train(b, dataset_id, model, **extra)
    assert response.status == 202, response.text
    run_id = response.json()['run_id']
    wait_for(b, run_id)
    assert b.get(f'/api/evaluate/{run_id}').json()['status'] == 'COMPLETED'
    return run_id


# ---- TC-AUTH-01: login with valid and invalid credentials (MLE-F-001, SR-001, SR-007) ----

def test_tc_auth_01(accounts, browser):
    b = browser(follow_redirects=False)
    # 1. Open the login page.
    page = b.get('/accounts/login/')
    assert page.status == 200 and 'name="password"' in page.text

    # 2. Valid username and password -> user reaches a logged-in page; session cookie is HttpOnly.
    answer = b.submit_form('/accounts/login/', {'username': 'ds_test1', 'password': PASSWORD})
    assert answer.status == 302
    assert 'HttpOnly' in answer.set_cookie('sessionid')
    assert b.get('/').status == 200                    # the dashboard opens for the logged-in user

    # 3. Log out.
    logout = b.request('POST', '/accounts/logout/', b'', 'application/x-www-form-urlencoded')
    assert logout.status == 302
    assert b.get('/').status == 302                    # back to the login page

    # 4. Valid username, wrong password -> refused with a generic error, no session created.
    fresh = browser(follow_redirects=False)
    refused = fresh.submit_form('/accounts/login/', {'username': 'ds_test1', 'password': 'Wrong#123'})
    assert refused.status == 200 and 'sessionid' not in refused.headers.get('Set-Cookie', '')
    api_refused = fresh.post_json('/api/auth/login', {'username': 'ds_test1', 'password': 'Wrong#123'})
    assert api_refused.status == 401
    assert api_refused.json()['error']['message'] == 'Invalid username or password.'
    assert fresh.cookie('sessionid') is None

    # 5. Stored password is a salted hash, never plain text.
    stored = get_user_model().objects.get(username='ds_test1').password
    assert stored.startswith('pbkdf2_sha256$') and PASSWORD not in stored

    # 6. Registration with a weak password is refused with a message per faulty field.
    weak = fresh.post_json('/api/auth/register', {
        'username': 'weak_user', 'email': 'weak@example.com', 'password': 'short1', 'role': 'STUDENT'})
    assert weak.status == 400
    assert weak.json()['error']['details']['fields']['password']

    # 7. A deactivated account cannot log in. (Deactivation is done directly here; the
    #    Admin console that does it from the browser is US-37, not merged yet.)
    get_user_model().objects.filter(username='ds_test1').update(is_active=False)
    assert browser().api_login('ds_test1', PASSWORD).status == 401


@pytest.mark.xfail(strict=True, reason='Observation O-5: login lands on /accounts/ (a Welcome page), '
                                       'TC-AUTH-01 step 2 expects the dashboard; owner Tejas (LOGIN_REDIRECT_URL)')
def test_tc_auth_01_step_2_login_lands_on_the_dashboard(accounts, browser):
    b = browser(follow_redirects=False)
    answer = b.submit_form('/accounts/login/', {'username': 'ds_test1', 'password': PASSWORD})
    assert answer.headers['Location'] == '/'


# ---- TC-DATA-01: upload a valid CSV and view its profile (MLE-F-003, F-004) ----

def test_tc_data_01(accounts, browser):
    b = browser('ds_test1')
    df = sample_1000rows()
    # 1-2. Open the Upload page, select a valid CSV and submit.
    assert b.get('/datasets/').status == 200
    response = b.upload('sample_1000rows.csv', csv_bytes(df))
    assert response.status == 201
    dataset = response.json()['dataset']

    # File accepted and saved in the user's own directory.
    stored = Path(Dataset.objects.get(pk=dataset['id']).file_path)
    assert stored.parent == Path(settings.DATA_ROOT) / str(accounts['ds'].id) / 'datasets'

    # 3. Preview: first rows shown; profile matches the file.
    assert (dataset['rows'], dataset['columns']) == (1000, 5)
    profile = {c['name']: c for c in dataset['profile']['columns']}
    assert list(profile) == list(df.columns)
    for column in df.columns:
        assert profile[column]['missing_values'] == int(df[column].isna().sum()), column
    assert {name: c['type'] for name, c in profile.items()} == {
        'age': 'numeric', 'income': 'numeric', 'city': 'categorical', 'score': 'numeric', 'bought': 'categorical'}
    assert len(dataset['profile']['preview']) == 20
    assert 'sample_1000rows.csv' in b.get('/datasets/').text


# ---- TC-DATA-02: reject invalid or unsafe uploads (MLE-F-003, F-015, SR-003) ----

def test_tc_data_02(accounts, browser):
    b = browser('ds_test1')
    # 1-2. Upload each invalid file in turn and observe the response.
    expected = {
        'notes.txt': (415, 'Only CSV files are supported.'),
        'empty.csv': (400, 'The file is empty.'),
        'no_header.csv': (400, 'The first row must be a header row with column names.'),
        'short_19rows.csv': (400, 'The file needs at least 20 data rows (found 19).'),
    }
    for name, (content, content_type) in INVALID_FILES.items():
        response = b.upload(name, content, content_type)
        assert (response.status, response.json()['error']['message']) == expected[name], name
        if response.status == 400:
            assert response.json()['error']['code'] == 'VALIDATION_ERROR'

    oversize = b.upload('oversize_11MB.csv', csv_of_exactly(11 * MB))
    assert oversize.status == 413
    assert oversize.json()['error']['message'] == 'The file is larger than 10 MB.'

    assert b.upload('exact_10MB.csv', csv_of_exactly(10 * MB)).status == 201

    # 4. No rejected file is stored: only exact_10MB.csv is in the file store.
    stored = list((Path(settings.DATA_ROOT) / str(accounts['ds'].id)).rglob('*.csv'))
    assert len(stored) == 1 and stored[0].stat().st_size == 10 * MB
    assert Dataset.objects.filter(owner=accounts['ds']).count() == 1


@pytest.mark.xfail(strict=True, reason='TC-DATA-02 step 3 needs the report export (US-26), not merged yet')
def test_tc_data_02_step_3_export_neutralises_formula_cells(accounts, browser):
    b = browser('ds_test1')
    run_id = completed_run(b, upload_iris(b))
    report = b.get(f'/api/runs/{run_id}/report?format=csv')
    assert report.status == 200
    assert not any(line.startswith(('=', '+', '-', '@')) for cell_line in report.text.splitlines()
                   for line in cell_line.split(','))


# ---- TC-MODEL-01: select a model, set parameters and train (MLE-F-006 to F-009, SR-006) ----

def test_tc_model_01(accounts, browser, settings):
    b = browser('student_test1')
    dataset_id = upload_iris(b)
    # 1-2. 80/20 split, Logistic Regression.  3. A valid C, then an out-of-range C.
    valid = b.post_json('/api/models/logistic_regression/params/validate', {'params': {'C': 1.0}})
    assert valid.status == 200 and valid.json()['params']['C'] == 1.0
    too_big = b.post_json('/api/models/logistic_regression/params/validate', {'params': {'C': 101}})
    assert too_big.status == 400
    assert too_big.json()['error']['message'] == 'C must be a number between 0.01 and 100.'
    refused = train(b, dataset_id, params={'C': 101}, split={'test_size': 0.2})
    assert refused.status == 400 and 'between 0.01 and 100' in refused.json()['error']['message']

    # 4. Start training and watch the status: Queued, Running, Completed.
    settings.TRAINING_WORKER_ENTRY = 'training.tests.faults.slow_success'   # 1.5 s longer, for step 5
    started = train(b, dataset_id, params={'C': 1.0}, split={'test_size': 0.2, 'random_state': 42})
    assert started.status == 202 and started.json()['status'] == 'QUEUED'
    run_id = started.json()['run_id']

    # 5. As a Student with one active job, start a second job: refused, limit stated.
    second = train(b, dataset_id)
    assert second.status == 429
    assert second.json()['error']['message'].startswith('You already have 1 training job in progress, '
                                                         'the limit for a Student.')

    seen = ['QUEUED'] + wait_for(b, run_id)
    assert b.get(f'/api/evaluate/{run_id}').json()['status'] == 'COMPLETED'
    seen.append('COMPLETED')
    assert seen[0] == 'QUEUED' and 'RUNNING' in seen and seen[-1] == 'COMPLETED', seen

    # Model artifact stored for this user only; run appears in history.
    artifact = ModelArtifact.objects.get(run__pk=run_id)
    assert artifact.owner == accounts['student']
    assert browser('ds_test1').get(f'/api/evaluate/{run_id}').status == 404
    assert [r['run_id'] for r in b.get('/api/runs').json()['runs']] == [run_id]


# ---- TC-EVAL-01: evaluation metrics and confusion matrix (MLE-F-010, F-011) ----

def test_tc_eval_01(accounts, browser):
    b = browser('ds_test1')
    dataset_id = upload_iris(b)
    run_id = completed_run(b, dataset_id, split={'test_size': 0.2, 'random_state': 42})
    # 1. Open the results page for the run.
    page = b.get(f'/runs/{run_id}/results/')
    assert page.status == 200 and 'id="confusion-matrix"' in page.text

    # 2-3. Read accuracy, precision, recall and F1, and the confusion matrix (what the page shows).
    shown = b.get(f'/api/evaluate/{run_id}').json()
    assert shown['averaging'] == 'macro'                  # three classes

    # 4. Compute the same metrics with scikit-learn on the same split and seed.
    run = Run.objects.get(pk=run_id)
    split = pipeline.load_split(run.dataset.file_path, 'species', 'median', 0.2, 42)
    predicted = load_artifact(accounts['ds'], run.artifact).predict(split.X_test)
    reference = {
        'accuracy': accuracy_score(split.y_test, predicted),
        'precision': precision_score(split.y_test, predicted, average='macro', zero_division=0),
        'recall': recall_score(split.y_test, predicted, average='macro', zero_division=0),
        'f1': f1_score(split.y_test, predicted, average='macro', zero_division=0),
    }
    for name, value in reference.items():
        assert shown['metrics']['test'][name] == pytest.approx(value, abs=0.001), name

    # Confusion matrix cell counts add up to the test set size.
    assert sum(map(sum, shown['confusion_matrix']['matrix'])) == len(split.y_test) == 24


# ---- TC-EXP-01: save and compare experiment runs (MLE-F-013, F-014) ----

def test_tc_exp_01_history(accounts, browser):
    b = browser('ds_test1')
    dataset_id = upload_iris(b)
    first = completed_run(b, dataset_id, 'logistic_regression')
    second = completed_run(b, dataset_id, 'random_forest', params={'n_estimators': 20})
    # 1-2. Open the experiment history; both runs are listed with dataset, model,
    #      parameters, metrics and time.
    runs = {r['run_id']: r for r in b.get('/api/runs').json()['runs']}
    assert list(runs) == [second, first]                      # newest first
    for run_id, model in ((first, 'logistic_regression'), (second, 'random_forest')):
        record = runs[run_id]
        assert (record['dataset_id'], record['model'], record['status']) == (dataset_id, model, 'COMPLETED')
        assert record['params'] and record['finished_at']
        assert {'test_accuracy', 'test_f1'} <= set(record['metrics'])
    assert runs[second]['params']['n_estimators'] == 20


@pytest.mark.xfail(strict=True, reason='TC-EXP-01 steps 3-4 need Compare (US-25), not merged yet')
def test_tc_exp_01_compare(accounts, browser):
    b = browser('ds_test1')
    dataset_id = upload_iris(b)
    first, second = completed_run(b, dataset_id), completed_run(b, dataset_id, 'knn')
    # 3. Select both and open Compare.
    compared = b.get(f'/api/runs/compare?ids={first},{second}')
    assert compared.status == 200
    # 4. Compare one of them with a run on a different dataset: refused with an explanation.
    other = completed_run(b, upload_iris(b))
    assert b.get(f'/api/runs/compare?ids={first},{other}').status == 422


# ---- TC-SEC-01: access control and data isolation (MLE-F-002, F-016, SR-005) ----

def test_tc_sec_01(accounts, browser):
    owner = browser('ds_test1')                               # User A
    dataset_id = upload_iris(owner)
    run_id = completed_run(owner, dataset_id)
    secret_values = ['setosa', 'sepal_length']                # data that must never leak

    # 1. As User B, request User A's dataset and run by changing the ID.
    other = browser('student_test1')                          # User B
    attempts = [
        other.get(f'/api/train/{run_id}'),
        other.get(f'/api/evaluate/{run_id}'),
        other.get(f'/runs/{run_id}/results/'),
        train(other, dataset_id),
        other.request('POST', '/api/datasets/preprocess',
                      f'dataset_id={dataset_id}&strategy=median'.encode(), 'application/x-www-form-urlencoded'),
    ]
    for response in attempts:
        assert response.status in (403, 404), response.status
        assert not any(value in response.text for value in secret_values)

    # 2. As User B, open an admin page: denied.
    assert other.get('/admin/').status == 403
    assert other.get('/accounts/admin-dashboard/').status == 403

    # 3. As Admin, open user management: the page opens.
    admin = browser(follow_redirects=False)
    assert admin.submit_form('/admin/login/?next=/admin/', {'username': 'admin_test1', 'password': PASSWORD}).status == 302
    users_page = admin.get('/admin/auth/user/')
    assert users_page.status == 200 and 'student_test1' in users_page.text

    # 4. The audit log shows the denied attempts with user ID and timestamp, and no data values.
    denied = AuditLog.objects.filter(action=Action.ACCESS_DENIED, user=accounts['student'])
    assert denied.count() >= len(attempts) + 1
    assert all(entry.timestamp for entry in denied)
    assert f'run:{run_id}' in {entry.target for entry in denied}
    assert not AuditLog.objects.filter(target__icontains='setosa').exists()

    # 5. As Admin, try to open the contents of User A's dataset: never the contents.
    for response in (
        admin.get('/datasets/'),
        admin.request('POST', '/api/datasets/preprocess',
                      f'dataset_id={dataset_id}&strategy=median'.encode(), 'application/x-www-form-urlencoded'),
        admin.get('/admin/datasets/dataset/'),
        admin.get(f'/api/evaluate/{run_id}'),
    ):
        assert response.status in (302, 403, 404), response.status
        assert not any(value in response.text for value in secret_values)
