"""Audit entries written automatically by Django's own events (US-38, MLE-SR-005(b)).

Django announces every login, logout and failed login through signals, for the
web form and the JSON API alike, so no login code needs to know about the audit
log. Registration and the lockout are logged where they happen
(accounts/views.py, accounts/api.py and accounts/forms.py).
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from . import services
from .models import Action


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    services.record(Action.LOGIN_SUCCESS, user=user, request=request)


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    # ``user`` is None if nobody was logged in; record() copes with that.
    services.record(Action.LOGOUT, user=user, request=request)


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request=None, **kwargs):
    # Only the username is read. The password in ``credentials`` is never touched.
    services.record_login_failed(credentials.get('username'), request=request)
