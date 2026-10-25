"""US-08: POST /api/train and GET /api/train/<run_id> (MLE-F-009; SAD 4.3.4, 4.4.2; TC-MODEL-01)."""
import json

import pytest

from experiments.models import Run

from .conftest import make_frame, store_dataset

pytestmark = pytest.mark.django_db


def train(client, body, capture=None):
    """POST /api/train. Pass ``django_capture_on_commit_callbacks`` to let the job run."""
    data = body if isinstance(body, (str, bytes)) else json.dumps(body)
    if capture is None:
        return client.post('/api/train', data=data, content_type='application/json')
    with capture(execute=True):
        return client.post('/api/train', data=data, content_type='application/json')


def body_for(dataset, **extra):
    return {'dataset_id': dataset.pk, 'target_column': 'label', 'model': 'logistic_regression', **extra}


def error(response):
    return response.json()['error']


# ---- access ------------------------------------------------------------------

def test_anonymous_user_gets_401(client):
    response = train(client, {})
    assert response.status_code == 401
    assert error(response)['code'] == 'AUTH_REQUIRED'


def test_admin_is_forbidden(client, admin_user, dataset):
    client.force_login(admin_user)
    response = train(client, body_for(dataset))
    assert response.status_code == 403
    assert error(response)['code'] == 'FORBIDDEN'
    assert not Run.objects.exists()


def test_get_is_not_allowed_on_train(student_client):
    assert student_client.get('/api/train').status_code == 405


# ---- the happy path (TC-MODEL-01) --------------------------------------------

def test_valid_request_is_queued_with_202_and_the_sad_response(student_client, dataset):
    response = train(student_client, body_for(dataset, params={'C': 2.0}))
    assert response.status_code == 202
    data = response.json()
    run = Run.objects.get()
    assert data == {
        'run_id': run.pk,
        'status': 'QUEUED',
        'links': {
            'status': f'/api/train/{run.pk}',
            'run': f'/api/runs/{run.pk}',
            'evaluate': f'/api/evaluate/{run.pk}',
        },
    }
    assert run.owner == dataset.owner
    assert run.params_json == {'C': 2.0, 'max_iter': 200}
    assert run.preprocessing_json == {'missing': 'median', 'categorical': 'one_hot'}
    assert run.split_json == {'test_size': 0.2, 'random_state': 42}


def test_job_runs_after_the_response_and_the_run_becomes_trained(
        student_client, dataset, django_capture_on_commit_callbacks):
    response = train(student_client, body_for(dataset), django_capture_on_commit_callbacks)
    assert response.json()['status'] == 'QUEUED'
    run = Run.objects.get()
    assert run.status == Run.Status.TRAINED
    assert run.artifact is not None


def test_data_scientist_can_train(client, scientist, django_capture_on_commit_callbacks):
    dataset = store_dataset(scientist, make_frame())
    client.force_login(scientist)
    response = train(client, body_for(dataset, model='knn'), django_capture_on_commit_callbacks)
    assert response.status_code == 202
    assert Run.objects.get().status == Run.Status.TRAINED


# ---- 400 VALIDATION_ERROR ----------------------------------------------------

@pytest.mark.parametrize('raw', ['{not json', '[1]', b'\xff\xfe'])
def test_body_that_is_not_a_json_object(student_client, raw):
    response = train(student_client, raw)
    assert response.status_code == 400
    assert error(response)['code'] == 'VALIDATION_ERROR'


def test_parameter_outside_its_range_is_refused_before_training(student_client, dataset):
    # TC-MODEL-01 step 3: C = -5.
    response = train(student_client, body_for(dataset, params={'C': -5}))
    assert response.status_code == 400
    assert error(response)['message'] == 'C must be a number between 0.01 and 100.'
    assert error(response)['details']['field'] == 'params.C'
    assert not Run.objects.exists()


def test_all_body_problems_are_listed(student_client):
    response = train(student_client, {'model': 'svm', 'split': {'test_size': 0.05}})
    assert response.status_code == 400
    fields = {e['field'] for e in error(response)['details']['errors']}
    assert fields == {'dataset_id', 'target_column', 'model', 'split.test_size'}


def test_target_column_not_in_dataset(student_client, dataset):
    response = train(student_client, body_for(dataset, target_column='price'))
    assert response.status_code == 400
    assert error(response)['code'] == 'VALIDATION_ERROR'
    assert error(response)['details'] == {'field': 'target_column'}
    assert not Run.objects.exists()


def test_target_that_breaks_the_class_rule(client, student):
    dataset = store_dataset(student, make_frame(classes=('only',)))
    client.force_login(student)
    response = train(client, body_for(dataset))
    assert response.status_code == 400
    assert 'between 2 and 20 classes' in error(response)['message']


# ---- 404 and 422 -------------------------------------------------------------

def test_unknown_dataset_is_404(student_client, dataset):
    response = train(student_client, {**body_for(dataset), 'dataset_id': dataset.pk + 100})
    assert response.status_code == 404
    assert error(response)['code'] == 'NOT_FOUND'


def test_another_users_dataset_is_404_not_403(client, scientist, dataset):
    client.force_login(scientist)
    response = train(client, body_for(dataset))
    assert response.status_code == 404
    assert error(response)['message'] == 'We could not find that dataset.'
    assert not Run.objects.exists()


def test_split_that_cannot_be_stratified_is_422(client, student):
    dataset = store_dataset(student, make_frame(n_per_class=2))
    client.force_login(student)
    response = train(client, body_for(dataset, split={'test_size': 0.1}))
    assert response.status_code == 422
    assert error(response)['code'] == 'UNPROCESSABLE'
    assert not Run.objects.exists()


# ---- GET /api/train/<run_id> -------------------------------------------------

def test_status_of_a_trained_run(student_client, dataset, django_capture_on_commit_callbacks):
    run_id = train(student_client, body_for(dataset), django_capture_on_commit_callbacks).json()['run_id']
    response = student_client.get(f'/api/train/{run_id}')
    assert response.status_code == 200
    data = response.json()
    assert data['run_id'] == run_id
    assert data['status'] == 'TRAINED'
    assert data['dataset_id'] == dataset.pk
    assert data['model'] == 'logistic_regression'
    assert data['params'] == {'C': 1.0, 'max_iter': 200}
    assert data['error'] is None
    assert data['started_at'].endswith('Z') and data['finished_at'].endswith('Z')


def test_status_of_a_queued_run(student_client, dataset):
    run_id = train(student_client, body_for(dataset)).json()['run_id']
    data = student_client.get(f'/api/train/{run_id}').json()
    assert data['status'] == 'QUEUED'
    assert data['started_at'] is None and data['finished_at'] is None


def test_status_of_a_failed_run_shows_a_safe_error(student_client, dataset):
    run = Run.objects.create(
        owner=dataset.owner, dataset=dataset, target_column='label', model_name='knn',
        status=Run.Status.FAILED, error_message='The dataset file could not be read as a CSV file.')
    data = student_client.get(f'/api/train/{run.pk}').json()
    assert data['status'] == 'FAILED'
    assert data['error'] == {'code': 'TRAINING_FAILED',
                             'message': 'The dataset file could not be read as a CSV file.'}


def test_another_users_run_is_404(client, scientist, dataset):
    run = Run.objects.create(owner=dataset.owner, dataset=dataset, target_column='label', model_name='knn')
    client.force_login(scientist)
    response = client.get(f'/api/train/{run.pk}')
    assert response.status_code == 404
    assert error(response)['code'] == 'NOT_FOUND'


def test_status_access_rules(client, admin_user, student):
    assert client.get('/api/train/1').status_code == 401
    client.force_login(admin_user)
    assert client.get('/api/train/1').status_code == 403
    client.force_login(student)
    assert client.post('/api/train/1').status_code == 405
    assert client.get('/api/train/1').status_code == 404
