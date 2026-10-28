"""Request, rate and job limits against denial of service (US-39, MLE-SR-006; SAD 4.3.1, 4.4.3).

(a) A request body over 10 MB is refused with 413. Multipart uploads get a
    small allowance for the form envelope, so that a CSV file of exactly 10 MB
    (accepted by SRS Table 4.2-1) still reaches the upload validator, which
    checks the file size itself.
(b) At most 120 requests in any 60 seconds per logged-in user, and per IP
    address for anonymous requests; the 121st gets 429 with Retry-After.
(c) At most 2 queued or running training jobs per user, 1 for a Student;
    a further job gets 429 with a message that states the limit.
(d) The 300-second job time limit is enforced by the training runner (US-21).

All limits can be changed in settings (names below). The request counters are
kept in Django's cache: with the default in-memory cache they count per server
process; configuring a shared cache (for example Redis) makes them global.
"""
import math
import threading
import time

from django.conf import settings
from django.core.cache import cache

from accounts.models import Role

MB = 1024 * 1024
DEFAULT_MAX_REQUEST_BYTES = 10 * MB
MULTIPART_ALLOWANCE_BYTES = 64 * 1024
DEFAULT_REQUESTS_PER_MINUTE = 120
WINDOW_SECONDS = 60
DEFAULT_JOB_LIMITS = {Role.STUDENT: 1, Role.DATA_SCIENTIST: 2}

_rate_lock = threading.Lock()
job_quota_lock = threading.Lock()


# ---- (a) request size ----------------------------------------------------------

def max_request_bytes():
    return int(getattr(settings, 'MAX_REQUEST_BYTES', DEFAULT_MAX_REQUEST_BYTES))


def body_too_large(request):
    """True when the declared body size is over the limit (checked before the body is read)."""
    try:
        length = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        return False  # a malformed header is left to the server and Django
    limit = max_request_bytes()
    if request.content_type == 'multipart/form-data':
        limit += MULTIPART_ALLOWANCE_BYTES
    return length > limit


# ---- (b) request rate ----------------------------------------------------------

def requests_per_minute():
    return int(getattr(settings, 'RATE_LIMIT_PER_MINUTE', DEFAULT_REQUESTS_PER_MINUTE))


def client_key(request):
    """The logged-in user, or the IP address for anonymous requests."""
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return f'user:{user.pk}'
    return f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"


def hit(key, now=None):
    """Record one request for ``key``. Returns 0 if allowed, else seconds until the next is allowed.

    Sliding window: at most N requests in ANY 60 seconds, so a burst cannot
    slip through across a minute boundary.
    """
    now = time.time() if now is None else now
    limit = requests_per_minute()
    cache_key = f'wbmme-rate:{key}'
    with _rate_lock:
        recent = [t for t in cache.get(cache_key, []) if t > now - WINDOW_SECONDS]
        if len(recent) >= limit:
            cache.set(cache_key, recent, WINDOW_SECONDS)
            return max(1, math.ceil(recent[0] + WINDOW_SECONDS - now))
        recent.append(now)
        cache.set(cache_key, recent, WINDOW_SECONDS)
        return 0


# ---- (c) training job quota ----------------------------------------------------

def job_limit(user):
    """How many QUEUED or RUNNING jobs this user may have at once."""
    limits = {**DEFAULT_JOB_LIMITS, **getattr(settings, 'TRAINING_JOB_LIMITS', {})}
    return limits.get(user.role, 0)


def job_quota_message(user, limit):
    role = 'Student' if user.role == Role.STUDENT else 'Data Scientist'
    jobs = 'job' if limit == 1 else 'jobs'
    return (
        f'You already have {limit} training {jobs} in progress, the limit for a {role}. '
        'Wait for one to finish, then try again.'
    )
