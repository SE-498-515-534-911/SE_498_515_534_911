from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = 'audit'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # Connect the signal receivers that write the audit log (US-38).
        from . import signals  # noqa: F401
