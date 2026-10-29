"""US-38: uploads and training are logged (MLE-SR-005(b); SAD 4.4.4)."""
import json

import numpy as np
import pandas as pd
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from audit.models import Action, AuditLog
from datasets.models import Dataset
from experiments.models import Run
from training import jobs

from .conftest import make_run

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def storage(settings, tmp_path):
    """Files go to a temporary folder; training jobs run in the test's own thread."""
    settings.DATA_ROOT = tmp_path / 'data'
    settings.MODEL_ARTIFACT_ROOT = tmp_path / 'artifacts'
    settings.TRAINING_JOBS_INLINE = True


def actions():
    return list(AuditLog.objects.order_by('id').values_list('action', 'target'))


def csv_bytes(rows=30):
    rng = np.random.default_rng(0)
    frame = pd.DataFrame({'x1': rng.normal(size=rows), 'x2': rng.normal(size=rows),
                          'label': ['a', 'b'] * (rows // 2)})
    return frame.to_csv(index=False).encode()


def training_dataset(owner, tmp_path):
    """A dataset on disk that the real training job can learn from."""
    rng = np.random.default_rng(1)
    x = rng.normal(size=120)
    frame = pd.DataFrame({'x1': x, 'x2': rng.normal(size=120),
                          'label': np.where(x > 0, 'yes', 'no')})
    path = tmp_path / f'train_{owner.pk}.csv'
    frame.to_csv(path, index=False)
    return Dataset.objects.create(owner=owner, name='train.csv', file_path=str(path),
                                  size_bytes=path.stat().st_size, rows=120, columns=3)


# ---- UPLOAD -----------------------------------------------------------------------------

def test_a_successful_upload_is_logged_with_user_dataset_and_address(client, alice):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    response = client.post('/api/upload', {'file': SimpleUploadedFile(
        'secret_name.csv', csv_bytes(), content_type='text/csv')})
    assert response.status_code == 201
    dataset = Dataset.objects.get()
    entry = AuditLog.objects.get(action=Action.UPLOAD)
    assert entry.user == alice
    assert entry.target == f'dataset:{dataset.pk}'
    assert entry.ip_address == '127.0.0.1'


def test_the_file_name_and_contents_are_not_logged(client, alice):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    client.post('/api/upload', {'file': SimpleUploadedFile(
        'secret_name.csv', csv_bytes(), content_type='text/csv')})
    stored = json.dumps(list(AuditLog.objects.values()), default=str)
    assert 'secret_name' not in stored and 'x1' not in stored


def test_a_refused_upload_is_not_logged_as_an_upload(client, alice):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    response = client.post('/api/upload', {'file': SimpleUploadedFile(
        'notes.txt', b'hello', content_type='text/plain')})
    assert response.status_code == 415
    assert not AuditLog.objects.filter(action=Action.UPLOAD).exists()


# ---- training ---------------------------------------------------------------------------

def test_training_start_and_finish_are_logged_in_order_for_the_owner(
        client, alice, tmp_path, django_capture_on_commit_callbacks):
    dataset = training_dataset(alice, tmp_path)
    client.force_login(alice)
    AuditLog.objects.all().delete()
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post('/api/train', json.dumps({
            'dataset_id': dataset.pk, 'target_column': 'label', 'model': 'logistic_regression'}),
            content_type='application/json')
    assert response.status_code == 202
    run_id = response.json()['run_id']
    assert actions() == [(Action.TRAIN_START, f'run:{run_id}'), (Action.TRAIN_DONE, f'run:{run_id}')]
    assert {e.user for e in AuditLog.objects.all()} == {alice}


def test_a_failed_training_run_is_logged_as_failed(alice, tmp_path):
    dataset = training_dataset(alice, tmp_path)
    run = make_run(alice, dataset)               # logs TRAIN_START by itself
    AuditLog.objects.all().delete()
    from pathlib import Path
    Path(dataset.file_path).unlink()             # the job cannot read its data
    jobs.execute_run(run.pk)
    run.refresh_from_db()
    assert run.status == Run.Status.FAILED
    assert actions() == [(Action.TRAIN_FAIL, f'run:{run.pk}')]
    assert AuditLog.objects.get().user == alice


def test_a_run_that_fails_during_evaluation_is_logged_as_failed(
        client, alice, tmp_path):
    from training.artifacts import user_artifact_dir
    dataset = training_dataset(alice, tmp_path)
    run = make_run(alice, dataset)
    jobs.execute_run(run.pk)
    run.refresh_from_db()
    assert run.status == Run.Status.TRAINED
    (user_artifact_dir(alice) / run.artifact.file_name).write_bytes(b'tampered')

    client.force_login(alice)
    AuditLog.objects.all().delete()
    assert client.get(f'/api/evaluate/{run.pk}').json()['status'] == 'FAILED'
    assert (Action.TRAIN_FAIL, f'run:{run.pk}') in actions()


def test_training_entries_hold_only_the_run_id_not_settings_or_data(
        client, alice, tmp_path, django_capture_on_commit_callbacks):
    dataset = training_dataset(alice, tmp_path)
    client.force_login(alice)
    AuditLog.objects.all().delete()
    with django_capture_on_commit_callbacks(execute=True):
        client.post('/api/train', json.dumps({
            'dataset_id': dataset.pk, 'target_column': 'label', 'model': 'random_forest',
            'params': {'n_estimators': 77}}), content_type='application/json')
    stored = json.dumps(list(AuditLog.objects.values()), default=str)
    for secret in ('label', 'x1', 'random_forest', 'n_estimators', 'train.csv'):
        assert secret not in stored


def test_someone_elses_training_attempt_is_not_logged_as_training(
        client, alice, bob, tmp_path):
    dataset = training_dataset(alice, tmp_path)
    client.force_login(bob)
    AuditLog.objects.all().delete()
    response = client.post('/api/train', json.dumps({
        'dataset_id': dataset.pk, 'target_column': 'label', 'model': 'knn'}),
        content_type='application/json')
    assert response.status_code == 404
    assert not AuditLog.objects.filter(action=Action.TRAIN_START).exists()
    assert AuditLog.objects.filter(action=Action.ACCESS_DENIED, user=bob).exists()
