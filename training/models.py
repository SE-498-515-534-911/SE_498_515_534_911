from django.conf import settings
from django.db import models


class ModelArtifact(models.Model):
    """Record of a model file written by the system.

    Only files with a record here (and a matching signature) can be loaded.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='model_artifacts'
    )
    file_name = models.CharField(max_length=64, unique=True)
    signature = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.file_name} ({self.owner})'
