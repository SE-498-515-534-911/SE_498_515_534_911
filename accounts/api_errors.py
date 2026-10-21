"""The standard JSON error envelope of SAD 4.3.1 and the codes of SAD 4.4.2."""
import uuid

from django.http import JsonResponse
from django.views.csrf import csrf_failure as default_csrf_failure


def error_response(request, code, message, status, details=None):
    """One shape for every API error: {"error": {code, message, details, request_id}}."""
    request_id = request.headers.get('X-Request-ID') or uuid.uuid4().hex[:8]
    body = {
        'error': {
            'code': code,
            'message': message,
            'details': details or {},
            'request_id': request_id,
        }
    }
    return JsonResponse(body, status=status)


def csrf_failure(request, reason=''):
    """A POST without a valid CSRF token is refused with 403 (MLE-SR-007d).

    API calls get the JSON envelope; normal pages keep Django's own 403 page.
    """
    if request.path.startswith('/api/'):
        return error_response(
            request, 'FORBIDDEN', 'CSRF token missing or invalid.', 403
        )
    return default_csrf_failure(request, reason)
