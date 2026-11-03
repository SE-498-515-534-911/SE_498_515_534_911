from django.urls import path

from . import prepared_download, views

urlpatterns = [
    path("",views.dashboard,name="dashboard"),
    path("datasets/",views.dataset_workspace,name="dataset_workspace"),
    path("api/upload",views.upload_view,name="api-upload"),
    path(
        "api/datasets/preprocess",
        views.preprocess_dataset,
        name="dataset_preprocess",
    ),
    path(
        "api/datasets/<int:dataset_id>/prepared",
        prepared_download.download_prepared,
        name="api-dataset-prepared",
    ),
]
