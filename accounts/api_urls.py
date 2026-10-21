from django.urls import path

from . import api

# Mounted at /api/auth/ (SAD 4.3.2).
urlpatterns = [
    path('register', api.register, name='api_register'),
    path('login', api.login_view, name='api_login'),
    path('logout', api.logout_view, name='api_logout'),
]
