from django.urls import path

from . import views

urlpatterns = [
    path(
        "api/datasets/preprocess",
        views.preprocess_dataset,
        name="dataset_preprocess",
    ),
]
