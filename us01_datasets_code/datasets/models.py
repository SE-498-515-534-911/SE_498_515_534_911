from django.conf import settings
from django.db import models


class Dataset(models.Model):
    """One uploaded CSV file owned by one user (SAD 4.1.4)."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="datasets")
    name = models.CharField(max_length=255)          # display name only
    file_path = models.CharField(max_length=500)     # server-generated path
    size_bytes = models.PositiveIntegerField()
    rows = models.PositiveIntegerField()
    columns = models.PositiveIntegerField()
    profile_json = models.JSONField(default=list, blank=True)   # filled by US-03
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.name} ({self.owner_id})"
