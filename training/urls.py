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
    path('train', views.start_training, name='api-train'),
    path('train/<int:run_id>', views.training_status, name='api-train-status'),
    path('runs', views.run_history, name='api-run-history'),
path('runs/compare', views.compare_runs, name='api-run-compare'),
]
