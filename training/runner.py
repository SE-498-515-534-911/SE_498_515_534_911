"""Runs one training job and contains whatever goes wrong with it (US-21, MLE-NF-006).

The job runs in a freshly started Python process ("spawn": it works the same
on Windows and Linux and shares no memory or database connection with the web
server). The server thread only waits for it, with a time limit, and reads its
small result file. So each of these fails ONE run and nothing else:

* an exception or bad data inside training  -> reported in result.json
* a crash or kill (for example out of memory) -> process ends without result.json
* a job that never finishes                 -> killed at the time limit (SAD 4.4.3)

``JobFailed.code`` / ``.message`` are what the user sees (SAD 4.4.2); technical
detail goes to the server log only.

Settings: ``TRAINING_TIMEOUT_SECONDS`` (default 300) and
``TRAINING_JOB_ISOLATION`` (default True; tests switch it off for speed and run
the worker in the calling thread).
"""
import json
import logging
import multiprocessing

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_ENTRY = 'training.worker.run_job'
HEARTBEAT_SECONDS = 5

TRAINING_FAILED = 'TRAINING_FAILED'
TRAINING_TIMEOUT = 'TRAINING_TIMEOUT'

TIMEOUT_MESSAGE = 'Training took too long. Try a smaller dataset or a simpler model.'
CRASH_MESSAGE = (
    'Training stopped unexpectedly. The dataset or model may be too large for the server. '
    'Try a smaller dataset or a simpler model.'
)
INTERNAL_MESSAGE = (
    'Training failed because of an internal error. Please try again, '
    'and tell your administrator if it keeps happening.'
)


class JobFailed(Exception):
    def __init__(self, message, code=TRAINING_FAILED):
        super().__init__(message)
        self.message = message
        self.code = code


def timeout_seconds():
    return float(getattr(settings, 'TRAINING_TIMEOUT_SECONDS', DEFAULT_TIMEOUT_SECONDS))


def _entry():
    # A setting so the fault-injection tests can run a misbehaving worker.
    return import_string(getattr(settings, 'TRAINING_WORKER_ENTRY', DEFAULT_ENTRY))


def _wait(process, limit, on_tick):
    """Wait up to ``limit`` seconds, calling ``on_tick`` every few seconds. True if it finished."""
    waited = 0.0
    while waited < limit:
        step = min(HEARTBEAT_SECONDS, limit - waited)
        process.join(step)
        if not process.is_alive():
            return True
        waited += step
        on_tick()
    return False


def _run_in_new_process(entry, spec, limit, on_tick):
    """Start the job process and wait. Returns its exit code, or None if it had to be killed."""
    process = multiprocessing.get_context('spawn').Process(
        target=entry, args=(spec,), name=f"wbmme-job-{spec['run_id']}", daemon=True
    )
    process.start()
    try:
        if _wait(process, limit, on_tick):
            return process.exitcode
        process.kill()
        process.join(10)
        return None
    finally:
        if process.is_alive():  # pragma: no cover - defensive: never leave a stray process
            process.kill()


def _read_result(out_dir):
    try:
        return json.loads((out_dir / 'result.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def run(spec, out_dir, on_tick=lambda: None):
    """Run one job. Returns the path of the trained model file, or raises JobFailed."""
    entry = _entry()
    run_id = spec['run_id']
    if getattr(settings, 'TRAINING_JOB_ISOLATION', True):
        limit = timeout_seconds()
        exit_code = _run_in_new_process(entry, spec, limit, on_tick)
        if exit_code is None:
            logger.warning('Training run %s killed after %s seconds', run_id, limit)
            raise JobFailed(TIMEOUT_MESSAGE, TRAINING_TIMEOUT)
    else:
        try:
            entry(spec)
        except BaseException:  # noqa: BLE001 - a misbehaving entry is an internal error
            logger.exception('Training run %s raised in the worker', run_id)
            raise JobFailed(INTERNAL_MESSAGE) from None
        exit_code = 0

    result = _read_result(out_dir)
    if result is None:
        logger.error('Training run %s ended (exit code %s) without a result', run_id, exit_code)
        raise JobFailed(CRASH_MESSAGE)
    if result.get('ok'):
        model = out_dir / 'model.joblib'
        if not model.is_file():
            logger.error('Training run %s reported success but wrote no model', run_id)
            raise JobFailed(INTERNAL_MESSAGE)
        return model
    if result.get('kind') == 'data':
        raise JobFailed(str(result.get('message') or INTERNAL_MESSAGE))
    logger.error('Training run %s failed in the worker:\n%s', run_id, result.get('log', '(no log)'))
    raise JobFailed(INTERNAL_MESSAGE)
