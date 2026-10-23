
"""API views for dataset preprocessing."""

import pandas as pd
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from accounts.api_errors import error_response
from accounts.permissions import data_user_required
from .services import preprocess_dataframe


@data_user_required
@require_POST
def preprocess_dataset(request):
    """Accept a CSV upload, preprocess it, and return the resulting data."""
    uploaded_file = request.FILES.get("file")
    strategy = request.POST.get("strategy", "").strip()

    if uploaded_file is None:
        return error_response(
            request,
            "VALIDATION_ERROR",
            "A CSV file is required in the 'file' field.",
            400,
        )

    if not uploaded_file.name.lower().endswith(".csv"):
        return error_response(
            request,
            "VALIDATION_ERROR",
            "Only CSV files are supported.",
            400,
        )

    if not strategy:
        return error_response(
            request,
            "VALIDATION_ERROR",
            "A preprocessing strategy is required.",
            400,
        )

    try:
        dataframe = pd.read_csv(uploaded_file)
        processed = preprocess_dataframe(dataframe, strategy)
    except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return error_response(
            request,
            "VALIDATION_ERROR",
            str(exc),
            400,
        )

    return JsonResponse({
        "message": "Dataset preprocessing completed.",
        "strategy": strategy,
        "rows": len(processed),
        "columns": processed.columns.tolist(),
        "data": processed.to_dict(orient="records"),
    })
