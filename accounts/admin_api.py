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
from math import ceil

from .api_errors import error_response
from .models import Role
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
