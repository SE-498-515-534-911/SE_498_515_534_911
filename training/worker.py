"""The code that trains a model inside the job process (US-21, MLE-NF-006).

``run_job`` normally runs in a separate, freshly started Python process (see
``runner.py``). It never touches the database and never raises: whatever
happens it leaves a small ``result.json`` in its scratch folder, and a
``model.joblib`` next to it only when training succeeded.

result.json is one of:
    {"ok": true}
    {"ok": false, "kind": "data", "message": "<plain text for the user>"}
    {"ok": false, "kind": "internal", "log": "<traceback, for the server log only>"}

A process that dies without writing result.json (killed, out of memory,
native crash) is detected by the runner.
"""
import json
import os
import traceback
from pathlib import Path


def _write_result(out_dir, payload):
    """Write result.json atomically: the runner sees all of it or none of it."""
    temp = out_dir / 'result.json.tmp'
    temp.write_text(json.dumps(payload), encoding='utf-8')
    os.replace(temp, out_dir / 'result.json')


def _setup_django():
    """A spawned process starts empty; load the settings the server uses."""
    import django
    from django.apps import apps

    if not apps.ready:  # pragma: no cover - true only in a spawned job process
        django.setup()


def run_job(spec):
    """Train one model. ``spec`` holds plain values only (it crosses a process boundary).

    Keys: file_path, target_column, model_name, params, missing, test_size,
    random_state, out_dir.
    """
    out_dir = Path(spec['out_dir'])
    try:
        _setup_django()
        import joblib

        from training import pipeline

        try:
            fitted, _ = pipeline.train(
                spec['file_path'],
                spec['target_column'],
                spec['model_name'],
                spec['params'],
                spec['missing'],
                spec['test_size'],
                spec['random_state'],
            )
        except pipeline.DataError as exc:
            _write_result(out_dir, {'ok': False, 'kind': 'data', 'message': exc.message})
            return
        joblib.dump(fitted, out_dir / 'model.joblib')
        _write_result(out_dir, {'ok': True})
    except BaseException:  # noqa: BLE001 - MemoryError and the like are recorded, never raised
        _write_result(out_dir, {'ok': False, 'kind': 'internal', 'log': traceback.format_exc()})
