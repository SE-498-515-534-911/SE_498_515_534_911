"""Training API views (SAD 3.4: controllers delegate to the training services).

Errors use the team's standard envelope (SAD 4.3.1) and the codes of the
error catalogue (SAD 4.4.2) through ``accounts.api_errors.error_response``.
"""
from django.http import JsonResponse

from accounts.api_errors import error_response
from accounts.permissions import DATA_ROLES, get_role

from . import catalogue


def list_models(request):
    """GET /api/models: the fixed model catalogue (MLE-F-007, SAD 4.3.4).

    Returns every model with its default hyperparameters and permitted ranges
    so the Select Model screen can build its parameter form from data.
    Allowed roles: Data Scientist and Student (SAD 4.3.2).
    """
    if request.method != 'GET':
        return error_response(
            request, 'METHOD_NOT_ALLOWED', 'Only GET requests are allowed.', 405
        )
    if not request.user.is_authenticated:
        return error_response(request, 'AUTH_REQUIRED', 'Please log in to continue.', 401)
    if get_role(request.user) not in DATA_ROLES:
        return error_response(
            request, 'FORBIDDEN', 'You do not have permission to do this.', 403
        )
    return JsonResponse({'models': [m.describe() for m in catalogue.list_models()]})
