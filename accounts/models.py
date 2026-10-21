from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    STUDENT = 'student', 'Student'
    DATA_SCIENTIST = 'data_scientist', 'Data Scientist'
    ADMIN = 'admin', 'Admin'


class Profile(models.Model):
    """Holds the single role of an account."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile'
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.STUDENT
    )

    def __str__(self):
        return f'{self.user} ({self.get_role_display()})'
