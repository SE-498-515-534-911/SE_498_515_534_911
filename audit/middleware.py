"""ACCESS_DENIED entries for refused requests (US-38, MLE-SR-005; TC-SEC-01).

Sits right after AuthenticationMiddleware, so it sees the final answer of every
view and of the role middleware, and logs two kinds of refusal for a logged-in
user:

* any ``403`` (a role that is not allowed, a missing CSRF token, ...);
* a ``404`` where the item exists but belongs to someone else. The user is told
  "not found" (SAD DD4, so the answer does not reveal the item exists), but the
  Admin can still see the attempt. A ``404`` for an item that does not exist at
  all is not logged: that is just a wrong address.

Only the method and path are logged, never the query string or the body.
"""
import json
import logging

from datasets.models import Dataset
from experiments.models import Run

from . import services
from .models import Action

logger = logging.getLogger(__name__)


def _dataset_id_sent_by(request):
    """The ``dataset_id`` a POST asked for (form field or JSON body), or None."""
    raw = request.POST.get('dataset_id')
    if raw is None and 'json' in (request.content_type or ''):
        body = json.loads(request.body or b'{}')
        raw = body.get('dataset_id') if isinstance(body, dict) else None
    if isinstance(raw, bool) or raw is None:
        return None
    return int(raw)


def _foreign_item(request, user):
    """``"run:5"`` or ``"dataset:3"`` if the request asked for someone else's item, else ''."""
    match = request.resolver_match
    if match is None:
        return ''                      # the address matched no page at all

    run_id = match.kwargs.get('run_id')
    if run_id is not None and Run.objects.filter(pk=run_id).exclude(owner=user).exists():
        return f'run:{run_id}'

    if request.method == 'POST':
        try:
            dataset_id = _dataset_id_sent_by(request)
        except (ValueError, TypeError):
            return ''                  # not a number, or not JSON: nothing to look up
        if dataset_id is not None and Dataset.objects.filter(pk=dataset_id).exclude(owner=user).exists():
            return f'dataset:{dataset_id}'
    return ''


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Remember where the request came from, for entries written by signals.
        token = services.current_ip.set(services.client_ip(request))
        try:
            response = self.get_response(request)
            self._log_denial(request, response)
            return response
        finally:
            services.current_ip.reset(token)

    def _log_denial(self, request, response):
        user = request.user
        if not user.is_authenticated or response.status_code not in (403, 404):
            return
        try:
            if response.status_code == 403:
                target = f'{request.method} {request.path}'
            else:
                target = _foreign_item(request, user)
                if not target:
                    return
            services.record(Action.ACCESS_DENIED, user=user, target=target)
        except Exception:  # noqa: BLE001 - a logging problem must never change the response
            logger.exception('Could not check a refused request for the audit log')
