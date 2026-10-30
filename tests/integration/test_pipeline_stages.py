"""US-28 integration tests: the pipeline stages in sequence (Test Plan section 5, Integration level).

Upload (datasets) -> Preprocess (datasets) -> Train (training) -> Evaluate
(evaluation) -> Record (experiments, audit), through the real API of each app,
with the real database and file store. Each test checks what every stage
hands to the next, and what it leaves behind.
"""
from pathlib import Path

import pytest
from django.conf import settings
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from audit.models import Action, AuditLog
from datasets.models import Dataset
from experiments.models import Run
from training import jobs, pipeline, recovery
from training.artifacts import load_artifact
from training.catalogue import list_models

from support.data import csv_bytes, iris_like

from .conftest import files_under

pytestmark = pytest.mark.django_db
MODELS = [m.key for m in list_models()]


def upload_iris(api):
    response = api.upload('iris_like.csv', csv_bytes(iris_like()))
    assert response.status_code == 201, response.content
    return response.json()['dataset']


def train_body(dataset_id, model='logistic_regression', **extra):
    return {'dataset_id': dataset_id, 'target_column': 'species', 'model': model, **extra}


def audit_actions(user):
    return [entry.action for entry in AuditLog.objects.filter(user=user).order_by('timestamp', 'id')]


# ---- the whole chain, once per catalogue model ------------------------------------

@pytest.mark.parametrize('model', MODELS)
def test_every_stage_hands_over_to_the_next(api, scientist, model):
    api.login(scientist)

    # Upload: file stored in the user's own folder, profile recorded.
    dataset = upload_iris(api)
    stored = Dataset.objects.get(pk=dataset['id'])
    assert Path(stored.file_path).parent == Path(settings.DATA_ROOT) / str(scientist.id) / 'datasets'
    assert (stored.rows, stored.columns) == (120, 5)

    # Preprocess: the saved dataset can be prepared (preview of the prepared table).
    prepared = api.preprocess(dataset['id'], 'median')
    assert prepared.status_code == 200
    assert prepared.json()['rows'] == 120

    # Train: the same dataset ID trains in the background.
    started = api.train(train_body(dataset['id'], model, split={'test_size': 0.25, 'random_state': 7}))
    assert started.status_code == 202
    run_id = started.json()['run_id']
    assert api.get(f'/api/train/{run_id}').json()['status'] == 'TRAINED'

    # Evaluate: the evaluation app loads the training app's signed model.
    evaluation = api.get(f'/api/evaluate/{run_id}').json()
    assert evaluation['status'] == 'COMPLETED'
    assert evaluation['averaging'] == 'macro'                       # three classes
    matrix = evaluation['confusion_matrix']
    assert sum(map(sum, matrix['matrix'])) == 30                    # 25% of 120 rows

    # Oracle (Test Plan 5): the shown metrics equal scikit-learn on the same split, within 0.001.
    run = Run.objects.get(pk=run_id)
    split = pipeline.load_split(stored.file_path, 'species', 'median', 0.25, 7)
    predicted = load_artifact(scientist, run.artifact).predict(split.X_test)
    test = evaluation['metrics']['test']
    assert test['accuracy'] == pytest.approx(accuracy_score(split.y_test, predicted), abs=0.001)
    for name, score in (('precision', precision_score), ('recall', recall_score), ('f1', f1_score)):
        expected = score(split.y_test, predicted, average='macro', zero_division=0)
        assert test[name] == pytest.approx(expected, abs=0.001), name

    # Record: run history shows the finished run with its configuration and metrics.
    history = api.get('/api/runs').json()['runs']
    assert [h['run_id'] for h in history] == [run_id]
    record = history[0]
    assert (record['status'], record['model'], record['dataset_id']) == ('COMPLETED', model, dataset['id'])
    assert record['split'] == {'test_size': 0.25, 'random_state': 7}
    assert record['metrics']['test_accuracy'] == pytest.approx(test['accuracy'])

    # Audit: each stage left an entry, without data values.
    assert audit_actions(scientist)[-3:] == [Action.UPLOAD, Action.TRAIN_START, Action.TRAIN_DONE]
    assert not AuditLog.objects.filter(target__icontains='setosa').exists()

    # File store: one dataset file, one model file, no half-finished job folders.
    assert len(files_under(Path(settings.DATA_ROOT) / str(scientist.id))) == 1
    assert len(files_under(Path(settings.MODEL_ARTIFACT_ROOT) / f'user_{scientist.id}')) == 1
    assert files_under(jobs.scratch_root()) == []


def test_preprocessing_choice_travels_from_the_request_to_the_evaluation(api, scientist):
    """drop_rows removes the 3 incomplete rows before the split, so the test split is smaller."""
    api.login(scientist)
    dataset = upload_iris(api)
    counts = {}
    for missing in ('median', 'drop_rows'):
        body = train_body(dataset['id'], preprocessing={'missing': missing, 'categorical': 'one_hot'},
                          split={'test_size': 0.5, 'random_state': 1})
        run_id = api.train(body).json()['run_id']
        matrix = api.get(f'/api/evaluate/{run_id}').json()['confusion_matrix']['matrix']
        counts[missing] = sum(map(sum, matrix))
    assert counts == {'median': 60, 'drop_rows': 59}
    recorded = {h['preprocessing']['missing'] for h in api.get('/api/runs').json()['runs']}
    assert recorded == {'median', 'drop_rows'}


def test_two_users_working_at_once_only_ever_see_their_own_data(api, scientist, student):
    api.login(scientist)
    own_run = api.train(train_body(upload_iris(api)['id'])).json()['run_id']
    api.login(student)
    other_dataset = upload_iris(api)['id']
    other_run = api.train(train_body(other_dataset, 'knn')).json()['run_id']

    for path in (f'/api/train/{own_run}', f'/api/evaluate/{own_run}', f'/runs/{own_run}/results/'):
        assert api.get(path).status_code == 404, path
    assert [h['run_id'] for h in api.get('/api/runs').json()['runs']] == [other_run]

    api.login(scientist)
    assert api.train(train_body(other_dataset)).status_code == 404
    assert [h['run_id'] for h in api.get('/api/runs').json()['runs']] == [own_run]


# ---- failures stop at the right stage and are reported everywhere -------------------

def test_a_request_that_fails_validation_leaves_no_trace_downstream(api, scientist):
    api.login(scientist)
    dataset = upload_iris(api)
    assert api.train(train_body(dataset['id'], params={'C': 101})).status_code == 400
    assert api.train(train_body(dataset['id'], target_column='colour')).status_code == 400
    assert api.get('/api/runs').json()['runs'] == []
    assert Action.TRAIN_START not in audit_actions(scientist)


def test_a_dataset_file_that_went_bad_is_refused_before_a_run_exists(api, scientist):
    api.login(scientist)
    dataset = upload_iris(api)
    Path(Dataset.objects.get(pk=dataset['id']).file_path).write_bytes(b'\xff\xfe broken')
    response = api.train(train_body(dataset['id']))
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'UNPROCESSABLE'
    assert api.get('/api/runs').json()['runs'] == []


def test_a_job_that_fails_is_reported_by_status_evaluation_history_and_audit(api, scientist, monkeypatch):
    api.login(scientist)
    dataset = upload_iris(api)

    def file_went_bad_after_the_request(*args, **kwargs):
        raise pipeline.DataError('The dataset file could not be read as a CSV file.', 'UNPROCESSABLE')

    monkeypatch.setattr('training.pipeline.train', file_went_bad_after_the_request)
    run_id = api.train(train_body(dataset['id'])).json()['run_id']

    status = api.get(f'/api/train/{run_id}').json()
    assert status['status'] == 'FAILED'
    assert status['error']['message'] == 'The dataset file could not be read as a CSV file.'
    evaluation = api.get(f'/api/evaluate/{run_id}').json()
    assert (evaluation['status'], evaluation['metrics']) == ('FAILED', None)
    assert evaluation['error']['message'] == status['error']['message']
    assert api.get('/api/runs').json()['runs'][0]['error_message'] == status['error']['message']
    assert audit_actions(scientist)[-1] == Action.TRAIN_FAIL
    assert files_under(Path(settings.MODEL_ARTIFACT_ROOT) / f'user_{scientist.id}') == []


def test_a_tampered_model_file_is_never_loaded_by_evaluation(api, scientist):
    """MLE-SR-004 across modules: training signs the file, evaluation checks the signature."""
    api.login(scientist)
    run_id = api.train(train_body(upload_iris(api)['id'])).json()['run_id']
    run = Run.objects.get(pk=run_id)
    model_file = Path(settings.MODEL_ARTIFACT_ROOT) / f'user_{scientist.id}' / run.artifact.file_name
    model_file.write_bytes(model_file.read_bytes() + b'tampered')

    evaluation = api.get(f'/api/evaluate/{run_id}').json()
    assert evaluation['status'] == 'FAILED'
    assert evaluation['metrics'] is None


def test_a_run_interrupted_by_a_restart_shows_as_failed_everywhere(api, scientist):
    api.login(scientist)
    dataset = Dataset.objects.get(pk=upload_iris(api)['id'])
    run = Run.objects.create(owner=scientist, dataset=dataset, target_column='species',
                             model_name='knn', status=Run.Status.RUNNING)
    assert recovery.fail_interrupted_runs(stale_after=0) == 1    # recover_runs --all at start-up

    message = 'Training was interrupted by a server restart. Please start it again.'
    assert api.get(f'/api/train/{run.pk}').json()['error']['message'] == message
    assert api.get(f'/api/evaluate/{run.pk}').json()['status'] == 'FAILED'
    assert api.get('/api/runs').json()['runs'][0]['error_message'] == message
