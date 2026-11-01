import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from datasets.models import Dataset


@login_required
def model_catalogue_page(request):
    return render(request, "training/models.html")


@login_required
def training_configuration_page(request):
    datasets = Dataset.objects.filter(
        owner=request.user
    ).order_by("-uploaded_at")

    for dataset in datasets:
        dataset.profile_json_text = json.dumps(dataset.profile_json)

    return render(
        request,
        "training/configuration.html",
        {"datasets": datasets},
    )