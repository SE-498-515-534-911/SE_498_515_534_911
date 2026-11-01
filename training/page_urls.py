from django.urls import path
from . import page_views

urlpatterns = [
    path("models/", page_views.model_catalogue_page, name="model_catalogue"),
    path("training/", page_views.training_configuration_page, name="training_configuration"),
]