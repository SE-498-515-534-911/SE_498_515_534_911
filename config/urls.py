"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('api/auth/', include('accounts.api_urls')),
    path('api/', include('training.urls')),
    path('api/evaluate/', include('evaluation.urls')),
    path('', include('datasets.urls')),
]
