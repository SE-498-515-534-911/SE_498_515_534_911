from django.shortcuts import render

from accounts.permissions import data_user_required
from .models import Run


@data_user_required
def experiments_page(request):
    """Display the current user's training runs and evaluation metrics."""
    runs = (
        Run.objects.filter(owner=request.user)
        .select_related("dataset")
        .prefetch_related("metrics")
        .order_by("-created_at", "-id")
    )

    return render(
        request,
        "experiments/list.html",
        {"runs": runs},
    )
