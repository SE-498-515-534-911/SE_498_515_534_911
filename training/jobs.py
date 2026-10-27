"""Background training jobs (US-08 MLE-F-009; US-21 MLE-NF-006; SAD DD1, 4.4.3).

``POST /api/train`` creates a Run in status QUEUED and returns at once. A
server thread then moves it to RUNNING and hands the work to ``runner``, which
trains in a separate process with a time limit. The thread only waits, sends a
heartbeat, and records the outcome: TRAINED with a signed model, or FAILED with
a plain message and a SAD 4.4.2 error code. Evaluation (US-10/22) then moves a
TRAINED run to COMPLETED.

A failed run never leaves a model behind: the worker writes into a private
scratch folder that is always deleted, and only a successful model is signed
and moved into the user's directory.
"""
import logging
import shutil
import threading
import uuid
from pathlib import Path

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from experiments.models import Run

from . import runner
from .artifacts import save_artifact_file

logger = logging.getLogger(__name__)

GENERIC_FAILURE = runner.INTERNAL_MESSAGE
SCRATCH_DIR_NAME = '_work'


def submit(run_id):
    """Start the job for ``run_id`` once the Run row is committed.

    With ``TRAINING_JOBS_INLINE = True`` (tests) the job runs in the caller's
    thread; otherwise it runs in a daemon thread.
    """
    def start():
        if getattr(settings, 'TRAINING_JOBS_INLINE', False):
            execute_run(run_id)
        else:
            threading.Thread(
                target=_thread_main, args=(run_id,), name=f'wbmme-train-{run_id}', daemon=True
            ).start()

    transaction.on_commit(start)


def _thread_main(run_id):
    close_old_connections()
    try:
        execute_run(run_id)
    finally:
        close_old_connections()


def scratch_root():
    """Private folder for unfinished jobs, outside the web root (inside MODEL_ARTIFACT_ROOT)."""
    return Path(settings.MODEL_ARTIFACT_ROOT) / SCRATCH_DIR_NAME


def _heartbeat(run_id):
    Run.objects.filter(pk=run_id, status=Run.Status.RUNNING).update(heartbeat_at=timezone.now())


def _finish(run, status, message='', code=''):
    """Record the outcome, but only if the run is still RUNNING (recovery may have failed it)."""
    now = timezone.now()
    updated = Run.objects.filter(pk=run.pk, status=Run.Status.RUNNING).update(
        status=status,
        error_message=message,
        error_code=code,
        artifact=run.artifact,
        finished_at=now,
        heartbeat_at=now,
    )
    return updated == 1


def execute_run(run_id):
    """Run one queued job to TRAINED or FAILED. Never raises."""
    run = Run.objects.select_related('dataset', 'owner').filter(
        pk=run_id, status=Run.Status.QUEUED
    ).first()
    if run is None:
        return
    now = timezone.now()
    run.status = Run.Status.RUNNING
    run.started_at = run.heartbeat_at = now
    run.save(update_fields=['status', 'started_at', 'heartbeat_at'])

    out_dir = scratch_root() / f'run_{run.pk}_{uuid.uuid4().hex[:8]}'
    try:
        out_dir.mkdir(parents=True)
        spec = {
            'run_id': run.pk,
            'file_path': run.dataset.file_path,
            'target_column': run.target_column,
            'model_name': run.model_name,
            'params': run.params_json,
            'missing': run.preprocessing_json.get('missing', 'median'),
            'test_size': run.split_json['test_size'],
            'random_state': run.split_json['random_state'],
            'out_dir': str(out_dir),
        }
        model_file = runner.run(spec, out_dir, on_tick=lambda: _heartbeat(run.pk))
        run.artifact = save_artifact_file(run.owner, model_file)
    except runner.JobFailed as exc:
        _finish(run, Run.Status.FAILED, exc.message, exc.code)
    except Exception:  # noqa: BLE001 - the cause goes to the server log, not to the user
        logger.exception('Training run %s failed', run_id)
        _finish(run, Run.Status.FAILED, GENERIC_FAILURE, runner.TRAINING_FAILED)
    else:
        if _finish(run, Run.Status.TRAINED):
            logger.info('Training run %s trained (%s)', run_id, run.model_name)
        else:
            # The run was marked FAILED meanwhile (interrupted); do not keep its model.
            _discard_artifact(run.artifact)
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def _discard_artifact(artifact):
    from .artifacts import user_artifact_dir

    (user_artifact_dir(artifact.owner) / artifact.file_name).unlink(missing_ok=True)
    artifact.delete()
