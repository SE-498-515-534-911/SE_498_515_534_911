"""Misbehaving training workers for the fault-injection tests (US-21, Test Plan 5: reliability).

Each function stands in for ``training.worker.run_job`` and runs in a real
child process, selected with the ``TRAINING_WORKER_ENTRY`` setting.
"""
import json
import os
import time
from pathlib import Path


def killed_without_result(spec):
    """Dies like a process killed by the operating system (for example out of memory)."""
    os._exit(137)


def raises_outside_the_worker(spec):
    """An exception that nothing in the job catches."""
    raise RuntimeError('boom outside the worker')


def half_written_model_then_crash(spec):
    """Writes part of a model file, then dies before reporting."""
    (Path(spec['out_dir']) / 'model.joblib').write_bytes(b'\x80\x04 partial')
    os._exit(1)


def hangs(spec):
    """Never finishes, so the runner has to stop it at the time limit."""
    time.sleep(3600)


def out_of_memory(spec):
    """Runs the real worker, but training runs out of memory."""
    from training import worker

    worker._setup_django()
    from training import pipeline

    def allocate_too_much(*args, **kwargs):
        return bytearray(10**13)  # 10 TB: raises MemoryError at once

    pipeline.train = allocate_too_much
    worker.run_job(spec)


def success_without_model(spec):
    """Reports success but writes no model file."""
    (Path(spec['out_dir']) / 'result.json').write_text(json.dumps({'ok': True}), encoding='utf-8')


def garbage_result(spec):
    """Leaves a result file that is not valid JSON."""
    (Path(spec['out_dir']) / 'result.json').write_text('{not json', encoding='utf-8')


def slow_success(spec):
    """Takes a moment, then trains for real (to observe heartbeats)."""
    time.sleep(1.5)
    from training import worker

    worker.run_job(spec)
