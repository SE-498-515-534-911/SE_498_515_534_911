"""POST /api/upload (SAD 4.3.3). Thin controller: check the caller, call the service, shape the JSON."""
from django.http import JsonResponse

from .errors import ApiError, ApiValidationError, AuthRequired, Forbidden, MethodNotAllowed, error_response
from .services import upload_dataset


def upload_view(request):
    try:
        if request.method != "POST":
            raise MethodNotAllowed("Use POST to upload a file.")
        if not request.user.is_authenticated:
            raise AuthRequired("Please log in to continue.")
        if getattr(request.user, "role", None) == "ADMIN":      # Admins cannot upload (SRS Table 4.1-1)
            raise Forbidden("You do not have permission to do this.")
        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise ApiValidationError("No file was uploaded.", field="file")
        ds = upload_dataset(request.user, uploaded, request.POST.get("name"))
    except ApiError as err:
        return error_response(err)
    return JsonResponse({"dataset_id": ds.id, "name": ds.name, "size_bytes": ds.size_bytes,
                         "rows": ds.rows, "columns": ds.columns, "profile": ds.profile_json,
                         "uploaded_at": ds.uploaded_at.isoformat()}, status=201)
