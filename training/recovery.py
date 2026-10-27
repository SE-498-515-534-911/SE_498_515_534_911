"""Restart recovery for training runs (US-21, MLE-NF-006, SAD 4.4.3).

A run is only QUEUED or RUNNING while a server thread is looking after it, and
that thread writes ``Run.heartbeat_at`` every few seconds. When the server
stops (restart, crash, deploy) the heartbeats stop too. Such a run can never
finish, so it is set to FAILED with "interrupted by server restart".

Two ways in:

* ``python manage.py recover_runs --all`` at start-up, before the server
  accepts requests: every QUEUED or RUNNING run is interrupted (SAD 4.4.3).
  This is the line to put in the Docker start command.
* Automatically, on the first request after the server starts and then at most
  every 30 seconds (``sweep_if_due``): only runs whose heartbeat has stopped
  for 60 seconds. This also covers ``runserver`` and is safe when several
  server processes run side by side, because a live run keeps beating.
"""
import logging
import shutil
import threading
import time
from datetime import timedelta

from django.db.models.functions import Coalesce
from django.utils import timezone

from experiments.models import Run

from . import runner

logger = logging.getLogger(__name__)

STALE_AFTER_SECONDS = 60
SWEEP_EVERY_SECONDS = 30
INTERRUPTED_MESSAGE = 'Training was interrupted by a server restart. Please start it again.'

_lock = threading.Lock()
_last_sweep = None


def fail_interrupted_runs(stale_after=STALE_AFTER_SECONDS):
    """Fail QUEUED/RUNNING runs with no sign of life for ``stale_after`` seconds. Returns the count.

    ``stale_after=0`` fails every active run (used at start-up, when none can be alive).
    """
    from .jobs import scratch_root

    now = timezone.now()
    active = Run.objects.filter(status__in=Run.ACTIVE_STATUSES)
    if stale_after:
        active = active.annotate(
            last_seen=Coalesce('heartbeat_at', 'started_at', 'created_at')
        ).filter(last_seen__lt=now - timedelta(seconds=stale_after))
    ids = list(active.values_list('pk', flat=True))
    if not ids:
        return 0
    count = Run.objects.filter(pk__in=ids, status__in=Run.ACTIVE_STATUSES).update(
        status=Run.Status.FAILED,
        error_code=runner.TRAINING_FAILED,
        error_message=INTERRUPTED_MESSAGE,
        finished_at=now,
    )
    for run_id in ids:  # remove anything an interrupted job left half-written
        for folder in scratch_root().glob(f'run_{run_id}_*'):
            shutil.rmtree(folder, ignore_errors=True)
    logger.warning('Marked %s interrupted training run(s) as FAILED: %s', count, ids)
    return count


def sweep_if_due(**kwargs):
    """``request_started`` receiver: run the recovery sweep on the first request, then every 30 s."""
    global _last_sweep
    with _lock:
        now = time.monotonic()
        if _last_sweep is not None and now - _last_sweep < SWEEP_EVERY_SECONDS:
            return
        _last_sweep = now
    try:
        fail_interrupted_runs()
    except Exception:  # noqa: BLE001 - recovery must never break a request
        logger.exception('Training run recovery sweep failed')
