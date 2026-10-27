"""US-21 fault-injection tests (MLE-NF-006; SAD 4.4.3; Test Plan 5: reliability).

These use REAL child processes: each failure must fail only its own run, leave
no model or scratch files, and leave the next job working.
"""
import multiprocessing
import time
from pathlib import Path

import pytest

from experiments.models import Run
from training import jobs, runner
from training.artifacts import load_artifact, user_artifact_dir
from training.models import ModelArtifact

from .conftest import make_frame, store_dataset

pytestmark = pytest.mark.django_db

FAULTS = 'training.tests.faults.'


@pytest.fixture(autouse=True)
def isolated(settings):
    settings.TRAINING_JOB_ISOLATION = True
    settings.TRAINING_TIMEOUT_SECONDS = 120


def make_run(dataset, **overrides):
    values = dict(
        owner=dataset.owner, dataset=dataset, target_column='label', model_name='decision_tree',
        params_json={'max_depth': None, 'min_samples_split': 2},
        preprocessing_json={'missing': 'median', 'categorical': 'one_hot'},
        split_json={'test_size': 0.2, 'random_state': 42},
    )
    values.update(overrides)
    return Run.objects.create(**values)


def run_with(settings, dataset, entry=None, **overrides):
    if entry:
        settings.TRAINING_WORKER_ENTRY = FAULTS + entry
    run = make_run(dataset, **overrides)
    jobs.execute_run(run.pk)
    run.refresh_from_db()
    return run


def assert_nothing_left(owner):
    assert not ModelArtifact.objects.exists()
    folder = user_artifact_dir(owner)
    assert not folder.exists() or not any(folder.iterdir())
    assert not any(jobs.scratch_root().glob('run_*'))
    assert multiprocessing.active_children() == []


# ---- the real worker in a real process ---------------------------------------

def test_real_job_in_a_separate_process_is_trained(settings, dataset):
    run = run_with(settings, dataset)
    assert run.status == Run.Status.TRAINED
    model = load_artifact(dataset.owner, run.artifact)
    assert model.named_steps['model'].__class__.__name__ == 'DecisionTreeClassifier'
    assert not any(jobs.scratch_root().glob('run_*'))
    assert multiprocessing.active_children() == []


def test_data_problem_in_the_child_is_shown_to_the_user(settings, dataset):
    run = run_with(settings, dataset, target_column='nope')
    assert run.status == Run.Status.FAILED
    assert run.error_code == 'TRAINING_FAILED'
    assert "'nope'" in run.error_message
    assert_nothing_left(dataset.owner)


# ---- injected faults: each fails one run, safely -------------------------------

@pytest.mark.parametrize('entry, message', [
    ('killed_without_result', runner.CRASH_MESSAGE),
    ('raises_outside_the_worker', runner.CRASH_MESSAGE),
    ('half_written_model_then_crash', runner.CRASH_MESSAGE),
    ('out_of_memory', runner.INTERNAL_MESSAGE),
    ('success_without_model', runner.INTERNAL_MESSAGE),
    ('garbage_result', runner.CRASH_MESSAGE),
])
def test_fault_fails_only_this_run_with_a_safe_message(settings, dataset, entry, message):
    run = run_with(settings, dataset, entry)
    assert run.status == Run.Status.FAILED
    assert run.error_code == 'TRAINING_FAILED'
    assert run.error_message == message
    assert run.finished_at is not None
    assert_nothing_left(dataset.owner)


def test_technical_detail_goes_to_the_log_only(settings, dataset, caplog):
    run = run_with(settings, dataset, 'out_of_memory')
    assert 'MemoryError' not in run.error_message
    assert 'MemoryError' in caplog.text


def test_job_that_never_finishes_is_stopped_at_the_time_limit(settings, dataset):
    settings.TRAINING_TIMEOUT_SECONDS = 2
    started = time.monotonic()
    run = run_with(settings, dataset, 'hangs')
    assert time.monotonic() - started < 30
    assert run.status == Run.Status.FAILED
    assert run.error_code == 'TRAINING_TIMEOUT'
    assert run.error_message == 'Training took too long. Try a smaller dataset or a simpler model.'
    assert_nothing_left(dataset.owner)


def test_next_job_works_after_a_crash(settings, dataset):
    crashed = run_with(settings, dataset, 'killed_without_result')
    settings.TRAINING_WORKER_ENTRY = runner.DEFAULT_ENTRY
    healthy = run_with(settings, dataset)
    assert (crashed.status, healthy.status) == (Run.Status.FAILED, Run.Status.TRAINED)


def test_other_users_runs_are_untouched_by_a_failure(settings, dataset, scientist):
    other = make_run(store_dataset(scientist, make_frame()))
    run_with(settings, dataset, 'killed_without_result')
    other.refresh_from_db()
    assert other.status == Run.Status.QUEUED


def test_heartbeat_is_written_while_the_job_runs(settings, dataset, monkeypatch):
    monkeypatch.setattr(runner, 'HEARTBEAT_SECONDS', 0.3)
    beats = []
    original = jobs._heartbeat
    monkeypatch.setattr(jobs, '_heartbeat', lambda run_id: (beats.append(run_id), original(run_id)))
    run = run_with(settings, dataset, 'slow_success')
    assert run.status == Run.Status.TRAINED
    assert len(beats) >= 2
    assert run.heartbeat_at >= run.started_at


# ---- in-process mode (used by the fast tests) ----------------------------------

def test_in_process_mode_contains_an_entry_that_raises(settings, dataset):
    settings.TRAINING_JOB_ISOLATION = False
    run = run_with(settings, dataset, 'raises_outside_the_worker')
    assert run.status == Run.Status.FAILED
    assert run.error_message == runner.INTERNAL_MESSAGE
    assert_nothing_left(dataset.owner)


def test_scratch_folder_problem_fails_the_run(settings, dataset, monkeypatch):
    settings.TRAINING_JOB_ISOLATION = False
    blocked = Path(settings.MODEL_ARTIFACT_ROOT)
    blocked.parent.mkdir(parents=True, exist_ok=True)
    blocked.write_text('a file where the folder should be')
    run = run_with(settings, dataset)
    assert run.status == Run.Status.FAILED
    assert run.error_message == jobs.GENERIC_FAILURE


def test_run_failed_by_recovery_meanwhile_keeps_failed_and_drops_its_model(settings, dataset, monkeypatch):
    settings.TRAINING_JOB_ISOLATION = False
    real_run = runner.run

    def interrupted_while_training(spec, out_dir, on_tick=lambda: None):
        model = real_run(spec, out_dir, on_tick)
        Run.objects.filter(pk=spec['run_id']).update(status=Run.Status.FAILED, error_message='interrupted')
        return model

    monkeypatch.setattr(runner, 'run', interrupted_while_training)
    run = run_with(settings, dataset)
    assert run.status == Run.Status.FAILED
    assert run.error_message == 'interrupted'
    assert run.artifact is None
    assert_nothing_left(dataset.owner)
