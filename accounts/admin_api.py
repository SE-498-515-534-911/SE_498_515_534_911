"""Admin console API (US-37, MLE-F-016; SAD 4.3.2, 4.3.7, 4.5.3).

Endpoints under ``/api/admin/``, for the Admin role only:

* ``GET    /api/admin/users``           list accounts with role and status
* ``PATCH  /api/admin/users/<id>``      change a role, deactivate or reactivate
* ``GET    /api/admin/datasets``        list dataset records (metadata only)
* ``DELETE /api/admin/datasets/<id>``   delete any dataset
* ``GET    /api/admin/audit``           read the audit log

The Admin manages accounts and dataset RECORDS. An Admin can never read what
is inside a dataset (MLE-F-016, SAD DD5): no response here contains file
contents, column profiles or file paths.
"""
import json
from math import ceil

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse, JsonResponse

from audit import services as audit
from audit.models import Action
from datasets.models import Dataset

from . import admin_services
from .api_errors import error_response
from .models import Profile, Role
from .permissions import get_role

DEFAULT_PAGE_SIZE = 20     # SAD 4.3.1
MAX_PAGE_SIZE = 100


def refuse_unless_admin(request, *allowed_methods):
    """Common checks for every admin endpoint: method, login, then role.

    Returns an error response, or None when the request may go ahead. Anyone
    who is not an Admin gets 403 and nothing else (MLE-F-002); the refusal is
    also written to the audit log by the audit middleware (US-38).
    """
    if request.method not in allowed_methods:
        allowed = ' or '.join(allowed_methods)
        return error_response(
            request, 'METHOD_NOT_ALLOWED', f'Use {allowed} for this endpoint.', 405
        )
    if not request.user.is_authenticated:
        return error_response(request, 'AUTH_REQUIRED', 'Please log in to continue.', 401)
    if get_role(request.user) != Role.ADMIN:
        return error_response(
            request, 'FORBIDDEN', 'You do not have permission to do this.', 403
        )
    return None


def paginate(request, queryset):
    """Cut ``queryset`` into the page asked for with ``?page=`` and ``?page_size=``.

    Defaults are page 1 and 20 per page, and at most 100 per page (SAD 4.3.1).
    Returns ``(items, meta, None)``, or ``(None, None, error_response)`` when the
    parameters are not valid numbers in range.
    """
    try:
        page = int(request.GET.get('page', 1))
        size = int(request.GET.get('page_size', DEFAULT_PAGE_SIZE))
    except ValueError:
        page = size = 0                     # falls through to the check below
    if page < 1 or not 1 <= size <= MAX_PAGE_SIZE:
        return None, None, error_response(
            request,
            'VALIDATION_ERROR',
            f'page must be 1 or more and page_size between 1 and {MAX_PAGE_SIZE}.',
            400,
            details={'field': 'page' if page < 1 else 'page_size'},
        )

    total = queryset.count()
    start = (page - 1) * size
    items = list(queryset[start:start + size])
    meta = {'page': page, 'page_size': size, 'total': total, 'pages': max(1, ceil(total / size))}
    return items, meta, None


def iso(moment):
    """A timestamp as ISO 8601 in UTC, like ``2026-10-20T09:30:00Z`` (SAD 4.3.1)."""
    return moment.isoformat().replace('+00:00', 'Z') if moment else None


# ---- users ---------------------------------------------------------------------

def _user_json(user):
    """One account for the Admin: who, which role and whether it can log in.

    Passwords, e-mail addresses and anything else about the person stay out:
    the Admin console needs only what is required to manage the account.
    """
    return {
        'id': user.pk,
        'username': user.username,
        'role': user.role,               # None for an account with no profile
        'is_active': user.is_active,
        'date_joined': iso(user.date_joined),
        'last_login': iso(user.last_login),
    }


def list_users(request):
    """GET /api/admin/users: every account with its role and status (MLE-F-016)."""
    refused = refuse_unless_admin(request, 'GET')
    if refused:
        return refused
    # select_related loads each profile in the same query, so the list does not
    # run one extra query per user to read its role.
    users = get_user_model().objects.select_related('profile').order_by('username')
    items, meta, error = paginate(request, users)
    if error:
        return error
    return JsonResponse({'users': [_user_json(u) for u in items], 'pagination': meta})


# ---- changing an account ---------------------------------------------------------

VALID_ROLES = {role.value for role in Role}
# The ONLY things an Admin can change through this endpoint. Anything else in the
# request (is_superuser, password, username, ...) is refused, so a crafted request
# cannot change fields it was never meant to touch.
CHANGEABLE_FIELDS = {'role', 'is_active'}


def _json_object(request):
    """The request body as a dict, or None when it is not a JSON object."""
    try:
        body = json.loads(request.body or b'')
    except (ValueError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _bad_request(request, message, field=None):
    details = {'field': field} if field else None
    return error_response(request, 'VALIDATION_ERROR', message, 400, details=details)


def update_user(request, user_id):
    """PATCH /api/admin/users/<id>: change a role, deactivate or reactivate (MLE-F-016).

    Body: ``{"role": "STUDENT"}``, ``{"is_active": false}`` or both. A role change
    takes effect on the account's very next request. A deactivated account cannot
    log in and its open sessions stop working, because Django treats an inactive
    user as not logged in.
    """
    refused = refuse_unless_admin(request, 'PATCH')
    if refused:
        return refused

    body = _json_object(request)
    if body is None:
        return _bad_request(request, 'The request body must be a JSON object.')
    unknown = set(body) - CHANGEABLE_FIELDS
    if unknown:
        return _bad_request(
            request, 'Only role and is_active can be changed.', field=sorted(unknown)[0]
        )
    if not body:
        return _bad_request(request, 'Give a role or is_active to change.')
    # Check the type first: a list or object is not a valid role (and cannot be looked up in a set).
    if 'role' in body and not (isinstance(body['role'], str) and body['role'] in VALID_ROLES):
        return _bad_request(
            request, 'role must be STUDENT, DATA_SCIENTIST or ADMIN.', field='role'
        )
    if 'is_active' in body and not isinstance(body['is_active'], bool):
        return _bad_request(request, 'is_active must be true or false.', field='is_active')

    target = get_user_model().objects.select_related('profile').filter(pk=user_id).first()
    if target is None:
        return error_response(request, 'NOT_FOUND', 'We could not find that account.', 404)
    if target.pk == request.user.pk:
        # An Admin who removes their own access could leave nobody able to manage accounts.
        return error_response(
            request, 'UNPROCESSABLE', 'You cannot change your own role or status.', 422
        )

    changes = []
    with transaction.atomic():
        if 'role' in body and body['role'] != target.role:
            Profile.objects.update_or_create(user=target, defaults={'role': body['role']})
            changes.append(f"role->{body['role']}")
        if 'is_active' in body and body['is_active'] != target.is_active:
            target.is_active = body['is_active']
            target.save(update_fields=['is_active'])
            changes.append('reactivated' if target.is_active else 'deactivated')
        if changes:
            # Audit log (US-38): who changed which account and how. No personal data.
            audit.record(
                Action.ADMIN_USER_UPDATE,
                user=request.user,
                target=f"user:{target.pk} {' '.join(changes)}",
                request=request,
            )

    refreshed = get_user_model().objects.select_related('profile').get(pk=target.pk)
    return JsonResponse({'user': _user_json(refreshed)})


# ---- datasets ----------------------------------------------------------------------

def _dataset_json(dataset):
    """A dataset RECORD for the Admin: name, owner, size and upload date (MLE-F-016).

    Never the file path, the row and column counts, the column profile or any
    cell value: the Admin manages the record, not the data (SAD DD5).
    """
    return {
        'id': dataset.pk,
        'name': dataset.name,
        'owner': {'id': dataset.owner_id, 'username': dataset.owner.username},
        'size_bytes': dataset.size_bytes,
        'uploaded_at': iso(dataset.uploaded_at),
    }


def list_datasets(request):
    """GET /api/admin/datasets: every dataset record, newest first (MLE-F-016)."""
    refused = refuse_unless_admin(request, 'GET')
    if refused:
        return refused
    datasets = Dataset.objects.select_related('owner').order_by('-uploaded_at', '-id')
    items, meta, error = paginate(request, datasets)
    if error:
        return error
    return JsonResponse({'datasets': [_dataset_json(d) for d in items], 'pagination': meta})


def delete_dataset(request, dataset_id):
    """DELETE /api/admin/datasets/<id>: remove any user's dataset (MLE-F-016).

    The file, the runs made from it and their model files go too. A dataset that
    a training job is still using is refused (422) so the job is not pulled out
    from under itself. The deletion is written to the audit log.
    """
    refused = refuse_unless_admin(request, 'DELETE')
    if refused:
        return refused

    dataset = Dataset.objects.select_related('owner').filter(pk=dataset_id).first()
    if dataset is None:
        return error_response(request, 'NOT_FOUND', 'We could not find that dataset.', 404)
    if admin_services.has_active_runs(dataset):
        return error_response(
            request,
            'UNPROCESSABLE',
            'This dataset is in use by a training job that has not finished. Try again later.',
            422,
        )

    # Note the identifiers now: after deletion the object no longer has them all.
    target = f'dataset:{dataset.pk} owner:{dataset.owner_id}'
    admin_services.remove_dataset(dataset)
    audit.record(Action.ADMIN_DATASET_DELETE, user=request.user, target=target, request=request)
    return HttpResponse(status=204)
