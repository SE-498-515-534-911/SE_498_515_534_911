"""The audit log (US-38, MLE-SR-005(b); SAD 3.9, 4.1.4, 4.4.4).

One row per important action: who did it, what, to which item, from which IP
address and when. The log never stores passwords, session IDs or dataset
contents (SAD 4.4.4), only short identifiers such as ``run:12``.
"""
from django.conf import settings
from django.db import models


class Action(models.TextChoices):
    """The audit events of SAD 4.4.4."""

    REGISTER = 'REGISTER', 'Register'
    LOGIN_SUCCESS = 'LOGIN_SUCCESS', 'Login succeeded'
    LOGIN_FAILED = 'LOGIN_FAILED', 'Login failed'
    LOGOUT = 'LOGOUT', 'Logout'
    UPLOAD = 'UPLOAD', 'Dataset uploaded'
    DATASET_DELETE = 'DATASET_DELETE', 'Dataset deleted'
    TRAIN_START = 'TRAIN_START', 'Training started'
    TRAIN_DONE = 'TRAIN_DONE', 'Training finished'
    TRAIN_FAIL = 'TRAIN_FAIL', 'Training failed'
    REPORT_EXPORT = 'REPORT_EXPORT', 'Report exported'
    ACCESS_DENIED = 'ACCESS_DENIED', 'Access denied'
    ADMIN_USER_UPDATE = 'ADMIN_USER_UPDATE', 'Admin changed a user'
    ADMIN_DATASET_DELETE = 'ADMIN_DATASET_DELETE', 'Admin deleted a dataset'


class AuditLog(models.Model):
    """One audit entry. Entries are only ever added, never changed."""

    # Null for events with no known account, such as a failed login for an
    # unknown username. If an account is deleted its entries stay.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_entries',
    )
    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)
    target = models.CharField(max_length=100, blank=True)   # e.g. "run:12", "user:3"
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp', '-id']

    def save(self, *args, **kwargs):
        # An audit trail that can be edited proves nothing: refuse any change.
        if not self._state.adding:
            raise ValueError('Audit log entries cannot be changed.')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.timestamp:%Y-%m-%d %H:%M:%S} {self.action} user={self.user_id} {self.target}'
