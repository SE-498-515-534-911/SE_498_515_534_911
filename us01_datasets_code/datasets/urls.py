from django.urls import path
from .views import upload_view

urlpatterns = [path("api/upload", upload_view, name="api-upload")]
