from django.conf import settings
from django.db import models


class Run(models.Model):
    """One training run: its configuration, status and trained model (SAD 4.1.4).

    Created by ``POST /api/train`` (US-08) in status QUEUED. The training job
    moves it to RUNNING and then TRAINED once the model is fitted and saved;
    evaluation (US-10) moves it to COMPLETED. Any error or time-out moves it to
    FAILED. Every query must filter by ``owner`` (MLE-SR-005).
    """

    class Status(models.TextChoices):
        QUEUED = 'QUEUED', 'Queued'
        RUNNING = 'RUNNING', 'Running'
        TRAINED = 'TRAINED', 'Trained'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    ACTIVE_STATUSES = (Status.QUEUED, Status.RUNNING)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='runs'
    )
    dataset = models.ForeignKey(
        'datasets.Dataset', on_delete=models.CASCADE, related_name='runs'
    )
    target_column = models.CharField(max_length=200)
    model_name = models.CharField(max_length=40)
    params_json = models.JSONField(default=dict)
    preprocessing_json = models.JSONField(default=dict)
    split_json = models.JSONField(default=dict)

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    error_message = models.TextField(blank=True, default='')
    # The trained model, stored and signed by training.artifacts (MLE-SR-004).
    artifact = models.OneToOneField(
        'training.ModelArtifact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='run',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'Run {self.pk} ({self.model_name}, {self.status})'
