
from django.urls import path

from . import views

urlpatterns = [
    path(
        "preprocess",
        views.preprocess_dataset,
        name="dataset_preprocess",
    ),
]
