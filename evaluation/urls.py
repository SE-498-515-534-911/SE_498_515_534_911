from django.urls import path

from . import views

# Mounted at /api/evaluate/ (SAD 4.3.2).
urlpatterns = [
    path('<int:run_id>', views.evaluate, name='api-evaluate'),
]
