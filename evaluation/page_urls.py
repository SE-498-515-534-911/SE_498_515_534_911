from django.urls import path

from . import views

# Mounted at the site root.
urlpatterns = [
    path('runs/<int:run_id>/results/', views.results_page, name='run-results'),
]
