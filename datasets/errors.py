
"""One error type and one JSON envelope for every API error (SAD 4.3.1 and 4.4)."""

import uuid

from django.http import JsonResponse


class ApiError(Exception):
    status = 400
    code = "VALIDATION_ERROR"

    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


class ApiValidationError(ApiError):
    status, code = 400, "VALIDATION_ERROR"


class AuthRequired(ApiError):
    status, code = 401, "AUTH_REQUIRED"


class Forbidden(ApiError):
    status, code = 403, "FORBIDDEN"


class PayloadTooLarge(ApiError):
    status, code = 413, "PAYLOAD_TOO_LARGE"


class UnsupportedMediaType(ApiError):
    status, code = 415, "UNSUPPORTED_MEDIA_TYPE"


class Unprocessable(ApiError):
    status, code = 422, "UNPROCESSABLE"


class MethodNotAllowed(ApiError):
    status, code = 405, "METHOD_NOT_ALLOWED"


def error_response(err):
    body = {
        "error": {
            "code": err.code,
            "message": err.message,
            "details": {"field": err.field} if err.field else {},
            "request_id": uuid.uuid4().hex[:8],
        }
    }
    return JsonResponse(body, status=err.status)
