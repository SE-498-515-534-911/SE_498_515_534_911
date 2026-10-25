from django.urls import path

from . import views

# Mounted at /api/ (SAD 4.3.2).
urlpatterns = [
    path('models', views.list_models, name='api-models'),
    path(
        'models/<str:key>/params/validate',
        views.validate_model_params,
        name='api-validate-params',
    ),
]
