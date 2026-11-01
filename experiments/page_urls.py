from django.urls import path

from . import views

urlpatterns = [
    path("experiments/", views.experiments_page, name="experiments"),
]