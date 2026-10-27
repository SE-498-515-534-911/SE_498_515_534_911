"""Fixtures for evaluation tests: real datasets, real trained runs (no mocks)."""
import pytest
from django.contrib.auth import get_user_model

from accounts.models import Role
from experiments.models import Run
from training import jobs
from training.tests.conftest import make_frame, store_dataset


@pytest.fixture(autouse=True)
def storage(settings, tmp_path):
    """Datasets and model files go to a temporary folder; jobs run in the test thread."""
    settings.MODEL_ARTIFACT_ROOT = tmp_path / 'artifacts'
    settings.DATA_ROOT = tmp_path / 'data'
    settings.TRAINING_JOBS_INLINE = True


def make_user(username, role):
    user = get_user_model().objects.create_user(username, f'{username}@example.com', 'Passw0rd1')
    user.profile.role = role
    user.profile.save()
    return user


@pytest.fixture
def student(db):
    return make_user('eval_student', Role.STUDENT)


@pytest.fixture
def scientist(db):
    return make_user('eval_scientist', Role.DATA_SCIENTIST)


@pytest.fixture
def admin_user(db):
    return make_user('eval_admin', Role.ADMIN)


@pytest.fixture
def other_user(db):
    return make_user('eval_other', Role.STUDENT)


def train_run(owner, model_name='logistic_regression', classes=('a', 'b', 'c'), params=None):
    """Create a dataset and a Run, and train it through the real training job."""
    dataset = store_dataset(owner, make_frame(classes=classes))
    run = Run.objects.create(
        owner=owner,
        dataset=dataset,
        target_column='label',
        model_name=model_name,
        params_json=params or {},
        preprocessing_json={'missing': 'median', 'categorical': 'one_hot'},
        split_json={'test_size': 0.2, 'random_state': 42},
    )
    jobs.execute_run(run.pk)
    run.refresh_from_db()
    assert run.status == Run.Status.TRAINED, run.error_message
    return run


@pytest.fixture
def trained_run(student):
    return train_run(student)
