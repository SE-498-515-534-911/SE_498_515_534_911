"""Training API views (SAD 3.4: controllers delegate to the training services).

Errors use the team's standard envelope (SAD 4.3.1) and the codes of the
error catalogue (SAD 4.4.2) through ``accounts.api_errors.error_response``.
"""
import json

from django.db import transaction
from django.http import JsonResponse

from accounts.api_errors import error_response
from accounts.permissions import DATA_ROLES, get_role
from datasets.models import Dataset
from experiments.models import Run

from . import catalogue, jobs, limits, pipeline
from .params import validate_params
from .schemas import parse_train_request


def _refuse(request, method):
    """Common checks for the training API: method, login, role (SAD 4.3.2).

    Returns an error response, or None when the request may go ahead.
    """
    if request.method != method:
        return error_response(
            request, 'METHOD_NOT_ALLOWED', f'Only {method} requests are allowed.', 405
        )
    if not request.user.is_authenticated:
        return error_response(request, 'AUTH_REQUIRED', 'Please log in to continue.', 401)
    if get_role(request.user) not in DATA_ROLES:
        return error_response(
            request, 'FORBIDDEN', 'You do not have permission to do this.', 403
        )
    return None


def _json_object(request):
    """The request body as a dict, or None when it is not a JSON object."""
    try:
        body = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _not_a_json_object(request):
    return error_response(
        request, 'VALIDATION_ERROR', 'The request body must be a JSON object.', 400
    )


def _validation_errors(request, errors):
    """400 VALIDATION_ERROR listing every problem; ``errors`` is [{field, message}]."""
    return error_response(
        request,
        'VALIDATION_ERROR',
        ' '.join(e['message'] for e in errors),
        400,
        details={'field': errors[0]['field'], 'errors': errors},
    )


def list_models(request):
    """GET /api/models: the fixed model catalogue (MLE-F-007, SAD 4.3.4).

    Returns every model with its default hyperparameters and permitted ranges
    so the Select Model screen can build its parameter form from data.
    Allowed roles: Data Scientist and Student (SAD 4.3.2).
    """
    refused = _refuse(request, 'GET')
    if refused:
        return refused
    return JsonResponse({'models': [m.describe() for m in catalogue.list_models()]})


def validate_model_params(request, key):
    """POST /api/models/<key>/params/validate: check hyperparameters (MLE-F-008).

    Body: ``{"params": {...}}``. Returns 200 with the complete parameter set
    (catalogue defaults filled in), or 400 VALIDATION_ERROR naming every
    parameter that is refused and its permitted range. ``POST /api/train``
    runs the same ``validate_params``, so this check cannot be skipped.
    """
    refused = _refuse(request, 'POST')
    if refused:
        return refused
    try:
        spec = catalogue.get_model(key)
    except catalogue.UnknownModel:
        return error_response(
            request, 'NOT_FOUND', f"There is no model called '{key}' in the catalogue.", 404
        )
    body = _json_object(request)
    if body is None:
        return _not_a_json_object(request)

    clean, errors = validate_params(spec.key, body.get('params'))
    if errors:
        return _validation_errors(request, [e.as_dict() for e in errors])
    return JsonResponse({'valid': True, 'model': spec.key, 'params': clean})


def _active_jobs(user):
    return Run.objects.filter(owner=user, status__in=Run.ACTIVE_STATUSES).count()


def _job_limit_reached(request, quota):
    return error_response(
        request,
        'RATE_LIMITED',
        limits.job_quota_message(request.user, quota),
        429,
        details={'limit': quota},
    )


def start_training(request):
    """POST /api/train: queue a background training job (MLE-F-009, SAD 4.3.4).

    Checks, in order: the body (400), that the dataset belongs to the caller
    (404, the same answer for "missing" and "someone else's", MLE-SR-005),
    and that the target column and split work on this dataset (400 / 422).
    Then it records a Run in status QUEUED, starts the job and returns 202
    at once. The client polls ``GET /api/train/<run_id>`` for the status.

    A user who already has the maximum number of QUEUED or RUNNING jobs gets
    429 RATE_LIMITED (Student 1, Data Scientist 2; MLE-SR-006(c), US-39).
    """
    refused = _refuse(request, 'POST')
    if refused:
        return refused
    body = _json_object(request)
    if body is None:
        return _not_a_json_object(request)
    parsed, errors = parse_train_request(body)
    if errors:
        return _validation_errors(request, errors)

    dataset = Dataset.objects.filter(pk=parsed.dataset_id, owner=request.user).first()
    if dataset is None:
        return error_response(request, 'NOT_FOUND', 'We could not find that dataset.', 404)

    quota = limits.job_limit(request.user)
    if _active_jobs(request.user) >= quota:
        return _job_limit_reached(request, quota)

    try:
        pipeline.load_split(
            dataset.file_path,
            parsed.target_column,
            parsed.preprocessing['missing'],
            parsed.split['test_size'],
            parsed.split['random_state'],
        )
    except pipeline.DataError as exc:
        status = 422 if exc.code == 'UNPROCESSABLE' else 400
        field = 'target_column' if status == 400 else None
        return error_response(
            request, exc.code, exc.message, status, details={'field': field} if field else None
        )

    # Check again and create in one step, so two quick requests cannot both pass.
    with limits.job_quota_lock, transaction.atomic():
        if _active_jobs(request.user) >= quota:
            return _job_limit_reached(request, quota)
        run = Run.objects.create(
            owner=request.user,
            dataset=dataset,
            target_column=parsed.target_column,
            model_name=parsed.model,
            params_json=parsed.params,
            preprocessing_json=parsed.preprocessing,
            split_json=parsed.split,
        )
        jobs.submit(run.pk)
    return JsonResponse(
        {
            'run_id': run.pk,
            'status': run.status,
            'links': {
                'status': f'/api/train/{run.pk}',
                'run': f'/api/runs/{run.pk}',
                'evaluate': f'/api/evaluate/{run.pk}',
            },
        },
        status=202,
    )


def _iso(moment):
    return moment.isoformat().replace('+00:00', 'Z') if moment else None


def training_status(request, run_id):
    """GET /api/train/<run_id>: status and configuration of one of the caller's runs.

    Another user's run answers 404, exactly like a run that does not exist.
    """
    refused = _refuse(request, 'GET')
    if refused:
        return refused
    run = Run.objects.filter(pk=run_id, owner=request.user).first()
    if run is None:
        return error_response(request, 'NOT_FOUND', 'We could not find that run.', 404)
    error = None
    if run.status == Run.Status.FAILED:
        error = {'code': run.error_code or 'TRAINING_FAILED', 'message': run.error_message}
    return JsonResponse({
        'run_id': run.pk,
        'status': run.status,
        'dataset_id': run.dataset_id,
        'target_column': run.target_column,
        'model': run.model_name,
        'params': run.params_json,
        'preprocessing': run.preprocessing_json,
        'split': run.split_json,
        'created_at': _iso(run.created_at),
        'started_at': _iso(run.started_at),
        'finished_at': _iso(run.finished_at),
        'error': error,
    })
