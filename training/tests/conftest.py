import pytest
from django.contrib.auth import get_user_model


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
