import pytest
from django.apps import apps
from django.conf import settings
from django.core.checks import Error, run_checks


def test_ci_setup():
    assert settings.configured
    assert apps.is_installed("accounts")
    assert apps.is_installed("datasets")


@pytest.mark.django_db
def test_django_system_checks():
    errors = run_checks()
    critical_errors = [
        error for error in errors
        if isinstance(error, Error)
    ]
    assert critical_errors == []
