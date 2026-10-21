"""Login throttling: 5 failed logins in 10 minutes block an account for 15
minutes (MLE-SR-007c, SAD 4.3.7). Used by both the HTML login and the JSON API.
"""
from datetime import timedelta

from django.utils import timezone

from .models import LoginThrottle

MAX_FAILURES = 5
FAILURE_WINDOW = timedelta(minutes=10)
LOCK_DURATION = timedelta(minutes=15)


def _key(username):
    return (username or '').strip().lower()


def is_locked(username):
    """True while the account is blocked."""
    record = LoginThrottle.objects.filter(username=_key(username)).first()
    return bool(record and record.locked_until and timezone.now() < record.locked_until)


def record_failure(username):
    """Count one failed login; start the 15 minute block on the 5th."""
    now = timezone.now()
    record, _ = LoginThrottle.objects.get_or_create(username=_key(username))

    # Failures older than 10 minutes no longer count: start a new window.
    if record.window_started_at is None or now - record.window_started_at > FAILURE_WINDOW:
        record.window_started_at = now
        record.failure_count = 0

    record.failure_count += 1
    if record.failure_count >= MAX_FAILURES:
        record.locked_until = now + LOCK_DURATION
        record.failure_count = 0
        record.window_started_at = None
    record.save()


def clear_failures(username):
    """A successful login ends the run of failures ("consecutive")."""
    LoginThrottle.objects.filter(username=_key(username)).delete()
