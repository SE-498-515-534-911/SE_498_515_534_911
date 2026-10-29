from django.urls import path

from . import admin_api

# Mounted at /api/admin/ (SAD 4.3.2).
urlpatterns = [
    path('users', admin_api.list_users, name='api-admin-users'),
    path('users/<int:user_id>', admin_api.update_user, name='api-admin-user'),
    path('audit', admin_api.list_audit, name='api-admin-audit'),
    path('datasets', admin_api.list_datasets, name='api-admin-datasets'),
    path('datasets/<int:dataset_id>', admin_api.delete_dataset, name='api-admin-dataset'),
]
