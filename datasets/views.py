
"""API views for dataset upload and profiling."""

from django.http import JsonResponse

from accounts.api_errors import error_response
from accounts.models import Role

from .errors import ApiError
from .services import upload_dataset


def upload_view(request):
    """Upload a CSV and return its metadata and profile."""
    if request.method != "POST":
        return error_response(
            request,
            "METHOD_NOT_ALLOWED",
            "Only POST requests are allowed.",
            405,
        )

    if not request.user.is_authenticated:
        return error_response(
            request,
            "AUTH_REQUIRED",
            "Authentication is required.",
            401,
        )

    if getattr(request.user, "role", None) not in (
        Role.STUDENT,
        Role.DATA_SCIENTIST,
    ):
        return error_response(
            request,
            "FORBIDDEN",
            "Your role does not allow dataset uploads.",
            403,
        )

    uploaded = request.FILES.get("file")
    if uploaded is None:
        return error_response(
            request,
            "VALIDATION_ERROR",
            "A CSV file is required in the 'file' field.",
            400,
            {"field": "file"},
        )

    try:
        dataset = upload_dataset(request.user, uploaded)
    except ApiError as err:
        details = {"field": err.field} if err.field else {}
        return error_response(
            request, err.code, err.message, err.status, details
        )

    return JsonResponse(
        {
            "dataset": {
                "id": dataset.id,
                "name": dataset.name,
                "size_bytes": dataset.size_bytes,
                "rows": dataset.rows,
                "columns": dataset.columns,
                "profile": dataset.profile_json,
                "uploaded_at": dataset.uploaded_at.isoformat(),
            }
        },
        status=201,
    )
