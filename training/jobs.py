"""Background training jobs (US-08, MLE-F-009; SAD DD1 and Figure 6 steps 3 to 6).

``POST /api/train`` creates a Run in status QUEUED and returns at once. A
worker thread moves it to RUNNING, fits the model, saves it through the signed
artifact store and sets TRAINED, so the user interface stays usable while a job
runs. Evaluation (US-10) then moves the run to COMPLETED. Any error moves it to
FAILED with a message that is safe to show the user.

Hardening for crashes and time-outs (US-21, US-39) builds on this module.
"""
import logging
import threading

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from experiments.models import Run

from . import pipeline
from .artifacts import save_artifact

logger = logging.getLogger(__name__)

GENERIC_FAILURE = (
    'Training failed because of an internal error. Please try again, '
    'and tell your administrator if it keeps happening.'
)


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


def _finish(run, status, error=''):
    run.status = status
    run.error_message = error
    run.finished_at = timezone.now()
    run.save(update_fields=['status', 'error_message', 'finished_at', 'artifact'])


def execute_run(run_id):
    """Run one queued job to TRAINED or FAILED. Never raises."""
    run = Run.objects.select_related('dataset', 'owner').filter(
        pk=run_id, status=Run.Status.QUEUED
    ).first()
    if run is None:
        return
    run.status = Run.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=['status', 'started_at'])
    try:
        fitted, _ = pipeline.train(
            run.dataset.file_path,
            run.target_column,
            run.model_name,
            run.params_json,
            run.preprocessing_json.get('missing', 'median'),
            run.split_json['test_size'],
            run.split_json['random_state'],
        )
        run.artifact = save_artifact(run.owner, fitted)
    except pipeline.DataError as exc:
        _finish(run, Run.Status.FAILED, exc.message)
    except Exception:  # noqa: BLE001 - the cause goes to the server log, not to the user
        logger.exception('Training run %s failed', run_id)
        _finish(run, Run.Status.FAILED, GENERIC_FAILURE)
    else:
        _finish(run, Run.Status.TRAINED)
        logger.info('Training run %s trained (%s)', run_id, run.model_name)
