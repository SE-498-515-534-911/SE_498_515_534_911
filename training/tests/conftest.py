import pytest
from django.contrib.auth import get_user_model

from accounts.models import Role


@pytest.fixture(autouse=True)
def artifact_root(settings, tmp_path):
    settings.MODEL_ARTIFACT_ROOT = tmp_path / 'artifacts'
    return settings.MODEL_ARTIFACT_ROOT


@pytest.fixture
def alice(db):
    return get_user_model().objects.create_user('alice', 'a@example.com', 'Passw0rd1')


@pytest.fixture
def bob(db):
    return get_user_model().objects.create_user('bob', 'b@example.com', 'Passw0rd1')


def _user_with_role(username, role):
    user = get_user_model().objects.create_user(username, f'{username}@example.com', 'Passw0rd1')
    user.profile.role = role
    user.profile.save()
    return user


@pytest.fixture
def student(db):
    return _user_with_role('train_student', Role.STUDENT)


@pytest.fixture
def scientist(db):
    return _user_with_role('train_scientist', Role.DATA_SCIENTIST)


@pytest.fixture
def admin_user(db):
    return _user_with_role('train_admin', Role.ADMIN)
