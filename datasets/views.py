"""API views for dataset upload and preprocessing."""

import pandas as pd

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from accounts.api_errors import error_response
from accounts.models import Role
from accounts.permissions import data_user_required

from .errors import ApiError
from .models import Dataset
from .services import preprocess_dataframe, upload_dataset

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
            request,
            err.code,
            err.message,
            err.status,
            details,
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


@data_user_required
@require_POST
def preprocess_dataset(request):
    """Preprocess a newly uploaded CSV or a saved dataset."""
    uploaded_file = request.FILES.get("file")
    dataset_id = request.POST.get("dataset_id", "").strip()
    strategy = request.POST.get("strategy", "").strip()

    if not strategy:
        return error_response(
            request,
            "VALIDATION_ERROR",
            "A preprocessing strategy is required.",
            400,
        )

    try:
        if uploaded_file is not None:
            if not uploaded_file.name.lower().endswith(".csv"):
                return error_response(
                    request,
                    "VALIDATION_ERROR",
                    "Only CSV files are supported.",
                    400,
                )

            dataframe = pd.read_csv(uploaded_file)

        elif dataset_id:
            try:
                dataset = Dataset.objects.get(
                    id=dataset_id,
                    owner=request.user,
                )
            except (Dataset.DoesNotExist, ValueError):
                return error_response(
                    request,
                    "VALIDATION_ERROR",
                    "Saved dataset not found.",
                    404,
                )

            dataframe = pd.read_csv(dataset.file_path)

        else:
            return error_response(
                request,
                "VALIDATION_ERROR",
                "Upload a CSV or select a saved dataset.",
                400,
            )

        processed = preprocess_dataframe(dataframe, strategy)

    except (
        ValueError,
        OSError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ) as exc:
        return error_response(
            request,
            "VALIDATION_ERROR",
            str(exc),
            400,
        )

    return JsonResponse(
        {
            "message": "Dataset preprocessing completed.",
            "strategy": strategy,
            "rows": len(processed),
            "columns": processed.columns.tolist(),
            "data": processed.to_dict(orient="records"),
        }
    )


@login_required
def dashboard(request):
    """Render the authenticated WBMME dashboard with user-owned dataset stats."""
    role = getattr(request.user, "role", None)
    if role not in (Role.STUDENT, Role.DATA_SCIENTIST):
        return render(request, "accounts/home.html", {"restricted_role": True})

    datasets = Dataset.objects.filter(owner=request.user)
    return render(
        request,
        "dashboard.html",
        {
            "dataset_count": datasets.count(),
            "recent_datasets": datasets[:5],
            "role_label": "Data Scientist" if role == Role.DATA_SCIENTIST else "Student",
        },
    )


@data_user_required
def dataset_workspace(request):
    """Show datasets owned by the current user and the preprocessing workspace."""
    datasets = Dataset.objects.filter(owner=request.user).order_by("-uploaded_at")
    return render(
        request,
        "datasets/workspace.html",
        {"datasets": datasets, "dataset_count": datasets.count()},
    )
