from django.urls import path

from . import admin_api

# Mounted at /api/admin/ (SAD 4.3.2).
urlpatterns = [
    path('users', admin_api.list_users, name='api-admin-users'),
]
