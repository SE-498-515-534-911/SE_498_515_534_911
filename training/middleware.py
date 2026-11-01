"""Request size and rate limits for every request (US-39, MLE-SR-006 (a) and (b); SAD 4.3.1).

Placed after AuthenticationMiddleware so the limit follows the logged-in user.
Static files are not counted. API paths get the standard JSON error envelope;
pages get a short plain-text answer.
"""
from django.conf import settings
from django.http import HttpResponse

from accounts.api_errors import error_response

from . import limits

TOO_LARGE_MESSAGE = 'The request is larger than 10 MB.'
# A file upload says "file", as the upload validator and SAD 4.4.2 do (found by TC-DATA-02, US-28).
FILE_TOO_LARGE_MESSAGE = 'The file is larger than 10 MB.'
RATE_LIMITED_MESSAGE = 'Too many requests. Please wait and try again.'


def _refuse(request, code, message, status):
    if request.path.startswith('/api/'):
        return error_response(request, code, message, status)
    return HttpResponse(message, status=status, content_type='text/plain; charset=utf-8')


class RequestLimitsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.static_prefix = '/' + settings.STATIC_URL.lstrip('/')

    def __call__(self, request):
        if request.path.startswith(self.static_prefix):
            return self.get_response(request)

        wait = limits.hit(limits.client_key(request))
        if wait:
            response = _refuse(request, 'RATE_LIMITED', RATE_LIMITED_MESSAGE, 429)
            response['Retry-After'] = str(wait)
            return response

        if limits.body_too_large(request):
            is_upload = request.content_type == 'multipart/form-data'
            message = FILE_TOO_LARGE_MESSAGE if is_upload else TOO_LARGE_MESSAGE
            return _refuse(request, 'PAYLOAD_TOO_LARGE', message, 413)

        return self.get_response(request)
