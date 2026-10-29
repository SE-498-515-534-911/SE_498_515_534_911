"""Writing audit entries (US-38, MLE-SR-005(b); SAD 4.4.4).

Everything that wants to leave a trace calls ``record``. It is deliberately
forgiving: if the entry cannot be written, the problem is logged on the server
and the user's request carries on, so a logging fault never blocks a login or
a training run.
"""
import ipaddress
import logging
from contextvars import ContextVar

from django.contrib.auth import get_user_model

from .models import Action, AuditLog

logger = logging.getLogger(__name__)

# The IP address of the request being handled, set by the audit middleware.
# It lets code that has no request in hand (such as a model signal) still
# record where the action came from.
current_ip = ContextVar('audit_current_ip', default=None)


def _valid_ip(value):
    """The address as text, or None if it is not a real IP address."""
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def client_ip(request):
    """Address the connection came from, as reported by the server (REMOTE_ADDR).

    The X-Forwarded-For header is NOT used: a client can set it to anything,
    which would let it write a false address into the log.
    """
    return _valid_ip(request.META.get('REMOTE_ADDR', ''))


def record(action, user=None, target='', request=None):
    """Add one entry. ``target`` is a short identifier such as ``run:12``.

    Never pass passwords, tokens or dataset contents: the log is read by Admins.
    """
    try:
        if user is not None and not getattr(user, 'pk', None):
            user = None                       # an anonymous visitor has no account
        ip = client_ip(request) if request is not None else current_ip.get()
        AuditLog.objects.create(
            user=user, action=action, target=str(target)[:100], ip_address=ip
        )
    except Exception:  # noqa: BLE001 - see the module docstring
        logger.exception('Audit entry %s could not be written', action)


def record_login_failed(username, request=None, target=''):
    """Log a failed login.

    The entry is linked to the account when the username exists, so an Admin
    can see attacks on one account. The typed username is never stored: people
    sometimes type their password into that box.
    """
    user = None
    if isinstance(username, str) and username:
        user = get_user_model().objects.filter(username__iexact=username).first()
    record(Action.LOGIN_FAILED, user=user, target=target, request=request)
