"""US-22: GET /api/evaluate/<run_id> (MLE-F-010, MLE-F-011, MLE-SR-005; SAD 4.3.5; TC-EVAL-01)."""
import json

import pytest

from experiments.models import Run
from training.artifacts import user_artifact_dir
from training.tests.conftest import make_frame, store_dataset

from .conftest import train_run

pytestmark = pytest.mark.django_db


def evaluate(client, run_id):
    return client.get(f'/api/evaluate/{run_id}')


def error(response):
    return response.json()['error']


# ---- access ------------------------------------------------------------------

def test_anonymous_user_gets_401(client, trained_run):
    response = evaluate(client, trained_run.pk)
    assert response.status_code == 401
    assert error(response)['code'] == 'AUTH_REQUIRED'


def test_admin_is_forbidden(client, admin_user, trained_run):
    client.force_login(admin_user)
    response = evaluate(client, trained_run.pk)
    assert response.status_code == 403
    assert error(response)['code'] == 'FORBIDDEN'


def test_another_users_run_is_404_exactly_like_a_missing_run(client, other_user, trained_run):
    client.force_login(other_user)
    other = evaluate(client, trained_run.pk)
    missing = evaluate(client, trained_run.pk + 999)
    assert other.status_code == missing.status_code == 404
    assert error(other)['message'] == error(missing)['message']
    assert 'metrics' not in other.json()          # nothing about the run leaks


def test_the_other_users_run_is_not_changed_by_the_attempt(client, other_user, trained_run):
    client.force_login(other_user)
    evaluate(client, trained_run.pk)
    trained_run.refresh_from_db()
    assert trained_run.status == Run.Status.TRAINED


def test_post_is_not_allowed(student_client, trained_run):
    assert student_client.post(f'/api/evaluate/{trained_run.pk}').status_code == 405


@pytest.fixture
def student_client(client, student):
    client.force_login(student)
    return client


@pytest.mark.parametrize('fixture', ['student', 'scientist'])
def test_student_and_data_scientist_can_read_their_own_results(client, request, fixture):
    user = request.getfixturevalue(fixture)
    run = train_run(user)
    client.force_login(user)
    assert evaluate(client, run.pk).status_code == 200


# ---- the SAD 4.3.5 response ----------------------------------------------------

def test_a_trained_run_returns_metrics_and_the_confusion_matrix(student_client, trained_run):
    response = evaluate(student_client, trained_run.pk)
    assert response.status_code == 200
    data = response.json()
    assert data['run_id'] == trained_run.pk
    assert data['status'] == 'COMPLETED'
    assert data['dataset_id'] == trained_run.dataset_id
    assert data['model'] == 'logistic_regression'
    assert data['averaging'] == 'macro'
    assert set(data['metrics']) == {'test', 'train'}
    assert set(data['metrics']['test']) == {'accuracy', 'precision', 'recall', 'f1', 'roc_auc'}
    assert data['confusion_matrix']['labels'] == ['a', 'b', 'c']
    assert data['error'] is None
    assert data['notes'] == []


def test_confusion_matrix_cells_add_up_to_the_test_rows(student_client, trained_run):
    """Acceptance criterion of US-22, checked through the API."""
    matrix = evaluate(student_client, trained_run.pk).json()['confusion_matrix']['matrix']
    # 3 classes x 40 rows = 120 rows, 20% test split = 24 test rows
    assert sum(sum(row) for row in matrix) == 24


def test_the_run_is_stored_as_completed_with_metric_rows(student_client, trained_run):
    evaluate(student_client, trained_run.pk)
    trained_run.refresh_from_db()
    assert trained_run.status == Run.Status.COMPLETED
    assert trained_run.metrics.count() == 10


def test_asking_again_gives_the_same_answer(student_client, trained_run):
    first = evaluate(student_client, trained_run.pk).json()
    second = evaluate(student_client, trained_run.pk).json()
    assert first == second
    assert trained_run.metrics.count() == 10


def test_a_two_class_run_reports_binary_averaging(student_client, student):
    run = train_run(student, classes=('yes', 'no'))
    data = evaluate(student_client, run.pk).json()
    assert data['averaging'] == 'binary'
    assert len(data['confusion_matrix']['matrix']) == 2


@pytest.mark.parametrize('status', [Run.Status.QUEUED, Run.Status.RUNNING])
def test_a_run_in_progress_is_200_with_null_metrics(student_client, student, status):
    run = Run.objects.create(
        owner=student, dataset=store_dataset(student, make_frame()), target_column='label',
        model_name='logistic_regression', status=status,
        split_json={'test_size': 0.2, 'random_state': 42},
    )
    response = evaluate(student_client, run.pk)
    assert response.status_code == 200          # polling must not look like an error
    data = response.json()
    assert data['status'] == status
    assert data['metrics'] is None and data['confusion_matrix'] is None
    assert data['error'] is None


def test_a_failed_training_run_shows_its_safe_error(student_client, student):
    run = Run.objects.create(
        owner=student, dataset=store_dataset(student, make_frame()), target_column='label',
        model_name='logistic_regression', status=Run.Status.FAILED,
        error_message='Training took too long.',
    )
    data = evaluate(student_client, run.pk).json()
    assert data['status'] == 'FAILED'
    assert data['metrics'] is None
    assert data['error'] == {'code': 'TRAINING_FAILED', 'message': 'Training took too long.'}


def test_a_broken_model_file_fails_the_run_without_leaking_details(student_client, trained_run):
    (user_artifact_dir(trained_run.owner) / trained_run.artifact.file_name).write_bytes(b'tampered')
    data = evaluate(student_client, trained_run.pk).json()
    assert data['status'] == 'FAILED'
    assert data['metrics'] is None
    assert 'integrity' not in json.dumps(data) and 'Traceback' not in json.dumps(data)
    assert data['error']['code'] == 'TRAINING_FAILED'


# ---- the whole flow -----------------------------------------------------------

def test_train_then_evaluate_end_to_end(student_client, student, django_capture_on_commit_callbacks):
    dataset = store_dataset(student, make_frame())
    body = {'dataset_id': dataset.pk, 'target_column': 'label', 'model': 'random_forest'}
    with django_capture_on_commit_callbacks(execute=True):
        started = student_client.post('/api/train', json.dumps(body), content_type='application/json')
    assert started.status_code == 202

    link = started.json()['links']['evaluate']           # the link the SAD promises
    data = student_client.get(link).json()
    assert data['status'] == 'COMPLETED'
    assert data['model'] == 'random_forest'
    assert sum(sum(row) for row in data['confusion_matrix']['matrix']) == 24


# ---- US-23: feature importance through the API ------------------------------------------

@pytest.mark.parametrize('model_name', ['logistic_regression', 'decision_tree', 'random_forest'])
def test_api_lists_features_in_descending_importance(student_client, student, model_name):
    run = train_run(student, model_name=model_name)
    data = evaluate(student_client, run.pk).json()
    ranking = data['feature_importance']
    assert [set(row) for row in ranking] == [{'feature', 'importance'}] * len(ranking)
    shares = [row['importance'] for row in ranking]
    assert shares == sorted(shares, reverse=True)
    assert data['feature_importance_message'] == ''


def test_api_says_not_available_for_knn(student_client, student):
    run = train_run(student, model_name='knn')
    data = evaluate(student_client, run.pk).json()
    assert data['status'] == 'COMPLETED'
    assert data['feature_importance'] is None
    assert data['feature_importance_message'] == (
        'Feature importance is not available for k-Nearest Neighbours.')


def test_no_importance_is_shown_before_the_run_is_evaluated(student_client, student):
    run = Run.objects.create(
        owner=student, dataset=store_dataset(student, make_frame()), target_column='label',
        model_name='random_forest', status=Run.Status.RUNNING)
    data = evaluate(student_client, run.pk).json()
    assert data['feature_importance'] is None and data['feature_importance_message'] == ''


def test_another_users_importance_is_not_exposed(client, other_user, trained_run):
    client.force_login(other_user)
    response = evaluate(client, trained_run.pk)
    assert response.status_code == 404
    assert 'feature_importance' not in response.json()
