"""Integration-test fixtures (US-28): real apps, real database and file store, Django test client."""
import json
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Role


@pytest.fixture(autouse=True)
def stores(settings, tmp_path):
    """Datasets and models go to a fresh folder per test; jobs run in the test's thread."""
    settings.DATA_ROOT = tmp_path / 'data'
    settings.MODEL_ARTIFACT_ROOT = tmp_path / 'models'
    settings.TRAINING_JOBS_INLINE = True
    return tmp_path


def make_user(username, role):
    user = get_user_model().objects.create_user(username, f'{username}@example.com', 'Passw0rd!x')
    user.profile.role = role
    user.profile.save()
    return user


@pytest.fixture
def scientist(db):
    return make_user('it_scientist', Role.DATA_SCIENTIST)


@pytest.fixture
def student(db):
    return make_user('it_student', Role.STUDENT)


class Api:
    """The Django test client, used the way the WBMME pages use the API."""

    def __init__(self, client, capture):
        self.client, self.capture = client, capture

    def login(self, user):
        self.client.force_login(user)
        return self

    def upload(self, name, content, content_type='text/csv'):
        return self.client.post('/api/upload', {'file': SimpleUploadedFile(name, content, content_type)})

    def preprocess(self, dataset_id, strategy):
        return self.client.post('/api/datasets/preprocess', {'dataset_id': dataset_id, 'strategy': strategy})

    def train(self, body):
        """POST /api/train; the job runs when the request's transaction commits, as on a server."""
        with self.capture(execute=True):
            return self.client.post('/api/train', data=json.dumps(body), content_type='application/json')

    def get(self, path):
        return self.client.get(path)


@pytest.fixture
def api(client, django_capture_on_commit_callbacks):
    return Api(client, django_capture_on_commit_callbacks)


def files_under(folder):
    folder = Path(folder)
    return sorted(p for p in folder.rglob('*') if p.is_file()) if folder.exists() else []
