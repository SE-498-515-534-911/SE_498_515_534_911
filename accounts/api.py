"""JSON auth API of SAD 4.3.7: register, login and logout (US-15, MLE-F-001).

Every error uses the envelope of SAD 4.3.1. Views are not csrf_exempt, so a
POST must carry the X-CSRFToken header (MLE-SR-007d). Plain passwords are
never logged or returned (MLE-SR-001).
"""
import json
from functools import wraps

from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, JsonResponse

from audit import services as audit
from audit.models import Action

from . import throttle
from .api_errors import error_response
from .forms import ApiRegistrationForm


def api_post(view):
    """Allow POST only; other methods get a JSON 405."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.method != 'POST':
            return error_response(
                request, 'METHOD_NOT_ALLOWED', 'Use POST for this endpoint.', 405
            )
        return view(request, *args, **kwargs)

    return wrapper


def _json_body(request):
    """Parse the request body as a JSON object, or return None."""
    try:
        data = json.loads(request.body or b'')
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _user_json(user):
    """The user shape of SAD 4.3.7: id, username and role."""
    return {'id': user.pk, 'username': user.username, 'role': user.role}


@api_post
def register(request):
    data = _json_body(request)
    if data is None:
        return error_response(
            request, 'VALIDATION_ERROR', 'Request body must be a JSON object.', 400
        )

    form = ApiRegistrationForm(data)
    if not form.is_valid():
        # One message list per faulty field (TC-AUTH-01 step 6).
        fields = {
            name: [e['message'] for e in errors]
            for name, errors in form.errors.get_json_data().items()
        }
        return error_response(
            request, 'VALIDATION_ERROR', 'Please correct the highlighted fields.',
            400, details={'field': next(iter(fields)), 'fields': fields},
        )

    user = form.save()
    audit.record(Action.REGISTER, user=user, target=f'user:{user.pk}', request=request)
    return JsonResponse({'user': _user_json(user)}, status=201)


@api_post
def login_view(request):
    data = _json_body(request)
    if data is None or not isinstance(data.get('username'), str) \
            or not isinstance(data.get('password'), str):
        return error_response(
            request, 'VALIDATION_ERROR', 'username and password are required.', 400
        )
    username, password = data['username'], data['password']

    # Lockout is checked before any credential check (SAD 4.2.1).
    if throttle.is_locked(username):
        # Django's credential check never runs for a locked account, so log it here.
        audit.record_login_failed(username, request=request, target='locked')
        return error_response(
            request, 'ACCOUNT_LOCKED',
            'Too many failed logins. Try again in 15 minutes.', 429,
        )

    # authenticate() returns None for a wrong password, an unknown user and a
    # deactivated account alike, so all three get the same answer (MLE-F-001).
    user = authenticate(request, username=username, password=password)
    if user is None:
        throttle.record_failure(username)
        return error_response(
            request, 'INVALID_CREDENTIALS', 'Invalid username or password.', 401
        )

    throttle.clear_failures(username)
    login(request, user)  # starts the session; the cookie is HttpOnly
    return JsonResponse({'user': _user_json(user)})


@api_post
def logout_view(request):
    if not request.user.is_authenticated:
        return error_response(
            request, 'AUTH_REQUIRED', 'Please log in to continue.', 401
        )
    logout(request)
    return HttpResponse(status=204)
