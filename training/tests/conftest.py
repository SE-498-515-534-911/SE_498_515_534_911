import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

from accounts.models import Role
from datasets.models import Dataset
from datasets.services import profile_csv


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


# ---- US-08: datasets on disk and inline training jobs ----------------------

@pytest.fixture(autouse=True)
def data_root(settings, tmp_path):
    """Every test gets its own dataset folder; training jobs run in the test's thread."""
    settings.DATA_ROOT = tmp_path / 'data'
    settings.TRAINING_JOBS_INLINE = True
    return settings.DATA_ROOT


def make_frame(n_per_class=40, classes=('a', 'b', 'c'), seed=0):
    """Balanced classes, 2 numeric and 1 text feature, with a few missing values."""
    rng = np.random.default_rng(seed)
    frames = [
        pd.DataFrame({
            'x1': rng.normal(i * 2, 1, n_per_class),
            'x2': rng.normal(-i, 1, n_per_class),
            'colour': rng.choice(['red', 'green', 'blue'], n_per_class),
            'label': label,
        })
        for i, label in enumerate(classes)
    ]
    df = pd.concat(frames, ignore_index=True)
    if len(df) > 7:
        df.loc[3, 'x1'] = np.nan
        df.loc[7, 'colour'] = np.nan
    return df


def store_dataset(owner, df, name='data.csv'):
    """Write ``df`` where the upload service would and create its Dataset record."""
    folder = Path(settings.DATA_ROOT) / str(owner.id) / 'datasets'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{uuid.uuid4().hex}.csv'
    df.to_csv(path, index=False)
    return Dataset.objects.create(
        owner=owner,
        name=name,
        file_path=str(path),
        size_bytes=path.stat().st_size,
        rows=len(df),
        columns=len(df.columns),
        profile_json=profile_csv(path),
    )


@pytest.fixture
def frame():
    return make_frame()


@pytest.fixture
def dataset(student, frame):
    return store_dataset(student, frame)


@pytest.fixture
def student_client(client, student):
    client.force_login(student)
    return client
