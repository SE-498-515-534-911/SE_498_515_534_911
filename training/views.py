"""Training API views (SAD 3.4: controllers delegate to the training services).

Errors use the team's standard envelope (SAD 4.3.1) and the codes of the
error catalogue (SAD 4.4.2) through ``accounts.api_errors.error_response``.
"""
import json

from django.http import JsonResponse

from accounts.api_errors import error_response
from accounts.permissions import DATA_ROLES, get_role

from . import catalogue
from .params import validate_params


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
    (US-08) runs the same ``validate_params``, so this check cannot be skipped.
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
    try:
        body = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        body = None
    if not isinstance(body, dict):
        return error_response(
            request, 'VALIDATION_ERROR', 'The request body must be a JSON object.', 400
        )

    clean, errors = validate_params(spec.key, body.get('params'))
    if errors:
        return error_response(
            request,
            'VALIDATION_ERROR',
            ' '.join(e.message for e in errors),
            400,
            details={'field': errors[0].as_dict()['field'], 'errors': [e.as_dict() for e in errors]},
        )
    return JsonResponse({'valid': True, 'model': spec.key, 'params': clean})
