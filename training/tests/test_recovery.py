"""US-21 restart recovery (MLE-NF-006; SAD 4.4.3) and the signed hand-over of model files."""
import logging
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from experiments.models import Run
from training import jobs, recovery
from training.artifacts import _signature, load_artifact, save_artifact_file, user_artifact_dir
from training.models import ModelArtifact

pytestmark = pytest.mark.django_db


def make_run(dataset, status, seen_seconds_ago=None, created_seconds_ago=0):
    run = Run.objects.create(owner=dataset.owner, dataset=dataset, target_column='label',
                             model_name='knn', status=status)
    now = timezone.now()
    Run.objects.filter(pk=run.pk).update(
        created_at=now - timedelta(seconds=created_seconds_ago),
        heartbeat_at=None if seen_seconds_ago is None else now - timedelta(seconds=seen_seconds_ago),
    )
    run.refresh_from_db()
    return run


def statuses(*runs):
    return [Run.objects.get(pk=r.pk).status for r in runs]


# ---- fail_interrupted_runs ---------------------------------------------------

def test_runs_whose_heartbeat_stopped_are_failed_as_interrupted(dataset):
    silent = make_run(dataset, Run.Status.RUNNING, seen_seconds_ago=120)
    alive = make_run(dataset, Run.Status.RUNNING, seen_seconds_ago=10)
    old_queued = make_run(dataset, Run.Status.QUEUED, created_seconds_ago=300)
    new_queued = make_run(dataset, Run.Status.QUEUED)
    done = make_run(dataset, Run.Status.TRAINED, seen_seconds_ago=999)

    assert recovery.fail_interrupted_runs() == 2
    assert statuses(silent, alive, old_queued, new_queued, done) == [
        'FAILED', 'RUNNING', 'FAILED', 'QUEUED', 'TRAINED']
    silent.refresh_from_db()
    assert silent.error_message == 'Training was interrupted by a server restart. Please start it again.'
    assert silent.error_code == 'TRAINING_FAILED'
    assert silent.finished_at is not None


def test_at_start_up_every_active_run_is_interrupted(dataset):
    runs = [make_run(dataset, Run.Status.RUNNING, seen_seconds_ago=1), make_run(dataset, Run.Status.QUEUED)]
    assert recovery.fail_interrupted_runs(stale_after=0) == 2
    assert statuses(*runs) == ['FAILED', 'FAILED']


def test_nothing_to_recover(dataset):
    make_run(dataset, Run.Status.COMPLETED)
    assert recovery.fail_interrupted_runs(stale_after=0) == 0


def test_scratch_files_of_interrupted_runs_are_removed(dataset):
    silent = make_run(dataset, Run.Status.RUNNING, seen_seconds_ago=120)
    alive = make_run(dataset, Run.Status.RUNNING, seen_seconds_ago=1)
    for run in (silent, alive):
        folder = jobs.scratch_root() / f'run_{run.pk}_abcd1234'
        folder.mkdir(parents=True)
        (folder / 'model.joblib').write_bytes(b'partial')
    recovery.fail_interrupted_runs()
    assert not any(jobs.scratch_root().glob(f'run_{silent.pk}_*'))
    assert any(jobs.scratch_root().glob(f'run_{alive.pk}_*'))


def test_management_command_for_start_up(dataset):
    make_run(dataset, Run.Status.RUNNING, seen_seconds_ago=1)
    out = StringIO()
    call_command('recover_runs', '--all', stdout=out)
    assert out.getvalue().strip() == '1 interrupted training run(s) marked as FAILED.'
    out = StringIO()
    call_command('recover_runs', stdout=out)
    assert out.getvalue().startswith('0 ')


# ---- the automatic sweep -----------------------------------------------------

@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(recovery, '_last_sweep', None)
    monkeypatch.setattr(recovery.time, 'monotonic', lambda: now[0])
    return now


def test_sweep_runs_on_the_first_request_then_every_30_seconds(dataset, clock, monkeypatch):
    calls = []
    monkeypatch.setattr(recovery, 'fail_interrupted_runs', lambda: calls.append(clock[0]))
    recovery.sweep_if_due()
    clock[0] += 29
    recovery.sweep_if_due()
    clock[0] += 1
    recovery.sweep_if_due()
    assert calls == [1000.0, 1030.0]


def test_first_request_after_start_fails_a_silent_run(client, student, dataset, clock):
    silent = make_run(dataset, Run.Status.RUNNING, seen_seconds_ago=120)
    client.force_login(student)
    response = client.get(f'/api/train/{silent.pk}')
    assert response.json()['status'] == 'FAILED'
    assert response.json()['error']['message'].startswith('Training was interrupted')


def test_a_failing_sweep_never_breaks_the_request(clock, monkeypatch, caplog):
    def broken():
        raise RuntimeError('database is locked')

    monkeypatch.setattr(recovery, 'fail_interrupted_runs', broken)
    with caplog.at_level(logging.ERROR, logger='training.recovery'):
        recovery.sweep_if_due()
    assert 'recovery sweep failed' in caplog.text


# ---- status endpoint shows the SAD error code --------------------------------

def test_status_endpoint_reports_a_timeout_code(client, student, dataset):
    run = make_run(dataset, Run.Status.FAILED)
    Run.objects.filter(pk=run.pk).update(error_code='TRAINING_TIMEOUT', error_message='Training took too long.')
    client.force_login(student)
    assert client.get(f'/api/train/{run.pk}').json()['error'] == {
        'code': 'TRAINING_TIMEOUT', 'message': 'Training took too long.'}


# ---- save_artifact_file ------------------------------------------------------

def test_worker_model_is_signed_and_moved_without_being_loaded(student, tmp_path):
    import joblib

    source = tmp_path / 'model.joblib'
    joblib.dump({'weights': [1, 2, 3]}, source)
    payload = source.read_bytes()
    artifact = save_artifact_file(student, source)
    assert not source.exists()
    assert artifact.signature == _signature(payload)
    assert (user_artifact_dir(student) / artifact.file_name).read_bytes() == payload
    assert load_artifact(student, artifact) == {'weights': [1, 2, 3]}


def test_moved_file_is_removed_if_recording_fails(student, tmp_path, monkeypatch):
    source = tmp_path / 'model.joblib'
    source.write_bytes(b'model')

    def refuse(**kwargs):
        raise RuntimeError('database down')

    monkeypatch.setattr(ModelArtifact.objects, 'create', refuse)
    with pytest.raises(RuntimeError):
        save_artifact_file(student, source)
    assert not any(user_artifact_dir(student).iterdir())
