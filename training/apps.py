from django.apps import AppConfig


class TrainingConfig(AppConfig):
    name = 'training'

    def ready(self):
        # Restart recovery (US-21): sweep for interrupted runs on the first
        # request and then every 30 seconds. No database access happens here.
        from django.core.signals import request_started

        from .recovery import sweep_if_due

        request_started.connect(sweep_if_due, dispatch_uid='training-recovery-sweep')
