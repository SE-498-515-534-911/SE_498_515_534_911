"""US-08: the background job runner (MLE-F-009, SAD DD1 and Figure 6 steps 3 to 6)."""
import logging
import threading

import pytest

from experiments.models import Run
from training import jobs
from training.artifacts import load_artifact

from .conftest import make_frame, store_dataset

pytestmark = pytest.mark.django_db


def make_run(dataset, **overrides):
    values = dict(
        owner=dataset.owner,
        dataset=dataset,
        target_column='label',
        model_name='logistic_regression',
        params_json={'C': 1.0, 'max_iter': 200},
        preprocessing_json={'missing': 'median', 'categorical': 'one_hot'},
        split_json={'test_size': 0.2, 'random_state': 42},
    )
    values.update(overrides)
    return Run.objects.create(**values)


def test_successful_run_is_trained_with_a_signed_artifact(dataset):
    run = make_run(dataset)
    jobs.execute_run(run.pk)
    run.refresh_from_db()
    assert run.status == Run.Status.TRAINED
    assert run.error_message == ''
    assert run.started_at <= run.finished_at
    model = load_artifact(dataset.owner, run.artifact)
    assert model.named_steps['model'].__class__.__name__ == 'LogisticRegression'
    assert model.named_steps['model'].C == 1.0


def test_artifact_cannot_be_loaded_by_another_user(dataset, scientist):
    from training.artifacts import ArtifactError

    run = make_run(dataset)
    jobs.execute_run(run.pk)
    run.refresh_from_db()
    with pytest.raises(ArtifactError):
        load_artifact(scientist, run.artifact)


def test_data_problem_fails_the_run_with_a_plain_message(dataset):
    run = make_run(dataset, target_column='missing_column')
    jobs.execute_run(run.pk)
    run.refresh_from_db()
    assert run.status == Run.Status.FAILED
    assert "'missing_column'" in run.error_message
    assert run.artifact is None
    assert run.finished_at is not None


def test_internal_error_is_logged_and_the_user_sees_a_generic_message(dataset, monkeypatch, caplog):
    def explode(*args, **kwargs):
        raise RuntimeError('secret internal detail')

    monkeypatch.setattr(jobs.pipeline, 'train', explode)
    run = make_run(dataset)
    with caplog.at_level(logging.ERROR, logger='training.jobs'):
        jobs.execute_run(run.pk)
    run.refresh_from_db()
    assert run.status == Run.Status.FAILED
    assert run.error_message == jobs.GENERIC_FAILURE
    assert 'secret internal detail' not in run.error_message
    assert 'secret internal detail' in caplog.text


def test_missing_dataset_file_fails_the_run(dataset):
    from pathlib import Path

    Path(dataset.file_path).unlink()
    run = make_run(dataset)
    jobs.execute_run(run.pk)
    run.refresh_from_db()
    assert run.status == Run.Status.FAILED
    assert 'could not be read' in run.error_message


def test_only_queued_runs_are_executed(dataset):
    assert jobs.execute_run(999999) is None
    run = make_run(dataset, status=Run.Status.TRAINED)
    jobs.execute_run(run.pk)
    run.refresh_from_db()
    assert run.status == Run.Status.TRAINED
    assert run.started_at is None


def test_hyperparameters_and_seed_reach_the_model(student):
    dataset = store_dataset(student, make_frame())
    run = make_run(dataset, model_name='random_forest',
                   params_json={'n_estimators': 15, 'max_depth': 3},
                   split_json={'test_size': 0.3, 'random_state': 9})
    jobs.execute_run(run.pk)
    run.refresh_from_db()
    forest = load_artifact(student, run.artifact).named_steps['model']
    assert (forest.n_estimators, forest.max_depth, forest.random_state) == (15, 3, 9)


def test_submit_waits_for_commit_then_runs_inline(dataset, django_capture_on_commit_callbacks):
    run = make_run(dataset)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        jobs.submit(run.pk)
    run.refresh_from_db()
    assert run.status == Run.Status.QUEUED
    assert len(callbacks) == 1
    callbacks[0]()
    run.refresh_from_db()
    assert run.status == Run.Status.TRAINED


def test_submit_starts_a_daemon_thread_when_not_inline(dataset, settings, monkeypatch,
                                                       django_capture_on_commit_callbacks):
    settings.TRAINING_JOBS_INLINE = False
    seen, done = [], threading.Event()
    monkeypatch.setattr(jobs, 'close_old_connections', lambda: None)

    def fake_execute(run_id):
        thread = threading.current_thread()
        seen.append((run_id, thread.name, thread.daemon))
        done.set()

    monkeypatch.setattr(jobs, 'execute_run', fake_execute)
    with django_capture_on_commit_callbacks(execute=True):
        jobs.submit(41)
    assert done.wait(timeout=5)
    assert seen == [(41, 'wbmme-train-41', True)]


def test_run_describes_itself(dataset):
    run = make_run(dataset)
    assert str(run) == f'Run {run.pk} (logistic_regression, QUEUED)'


def test_thread_main_closes_connections_even_on_error(monkeypatch):
    closed = []
    monkeypatch.setattr(jobs, 'close_old_connections', lambda: closed.append(1))

    def boom(run_id):
        raise RuntimeError('x')

    monkeypatch.setattr(jobs, 'execute_run', boom)
    with pytest.raises(RuntimeError):
        jobs._thread_main(1)
    assert closed == [1, 1]
