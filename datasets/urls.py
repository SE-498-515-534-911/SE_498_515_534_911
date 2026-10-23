from django.urls import path

from . import views

urlpatterns = [
    path("api/upload", views.upload_view, name="api-upload"),
    path(
        "api/datasets/preprocess",
        views.preprocess_dataset,
        name="dataset_preprocess",
    ),
]
