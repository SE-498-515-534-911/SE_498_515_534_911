"""Project-wide test settings."""
import pytest


@pytest.fixture(autouse=True)
def training_jobs_in_process(settings):
    """Run training workers in the test's own process, which is much faster.

    The fault-injection tests in training/tests/test_containment.py switch
    isolation back on to use real child processes (US-21).
    """
    settings.TRAINING_JOB_ISOLATION = False


@pytest.fixture(autouse=True)
def fresh_request_counters():
    """Each test starts with empty rate-limit counters (US-39)."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
