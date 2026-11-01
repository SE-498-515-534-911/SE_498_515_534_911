"""System-test fixtures (US-28): a live server on a real port, production-like training jobs.

Each test case of Test Plan Appendix A runs against ``live_server`` over real
HTTP, with jobs in a background thread and training in a separate process
(US-21), as in the deployed system.
"""
import time

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Role
from support.http import Browser

PASSWORD = 'Str0ng!Passw0rd'


@pytest.fixture(autouse=True)
def production_like(settings, tmp_path):
    settings.DATA_ROOT = tmp_path / 'data'
    settings.MODEL_ARTIFACT_ROOT = tmp_path / 'models'
    settings.TRAINING_JOBS_INLINE = False      # background thread, as on the server
    settings.TRAINING_JOB_ISOLATION = True     # training in its own process (US-21)


def make_account(username, role):
    """The dummy accounts of Appendix A: ds_test1, student_test1, admin_test1."""
    User = get_user_model()
    if role == Role.ADMIN:
        return User.objects.create_superuser(username, f'{username}@example.com', PASSWORD)
    user = User.objects.create_user(username, f'{username}@example.com', PASSWORD)
    user.profile.role = role
    user.profile.save()
    return user


@pytest.fixture
def accounts(transactional_db):
    return {
        'ds': make_account('ds_test1', Role.DATA_SCIENTIST),
        'student': make_account('student_test1', Role.STUDENT),
        'admin': make_account('admin_test1', Role.ADMIN),
    }


@pytest.fixture
def browser(live_server):
    """A new browser session; ``browser('ds_test1')`` returns one that is logged in."""
    def open_browser(username=None, follow_redirects=True):
        b = Browser(live_server.url, follow_redirects=follow_redirects)
        if username:
            assert b.api_login(username, PASSWORD).status == 200
        return b
    return open_browser


def wait_for(b, run_id, final=('TRAINED', 'COMPLETED', 'FAILED'), timeout=90):
    """Poll the run like the Training Status screen does; returns every status seen, in order."""
    seen, deadline = [], time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = b.get(f'/api/train/{run_id}').json()['status']
        if not seen or seen[-1] != status:
            seen.append(status)
        if status in final:
            return seen
        time.sleep(0.1)
    raise AssertionError(f'run {run_id} did not finish: {seen}')
