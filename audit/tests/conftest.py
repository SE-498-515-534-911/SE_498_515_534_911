"""Fixtures for audit and ownership tests: users with each role, and their items."""
import pytest
from django.contrib.auth import get_user_model

from accounts.models import Role
from datasets.models import Dataset
from experiments.models import Run


def make_user(username, role):
    user = get_user_model().objects.create_user(username, f'{username}@example.com', 'Passw0rd1')
    user.profile.role = role
    user.profile.save()
    return user


def make_dataset(owner, tmp_path, name='data.csv'):
    path = tmp_path / f'{owner.pk}_{name}'
    path.write_text('x,label\n' + '\n'.join(f'{i},{i % 2}' for i in range(30)), encoding='utf-8')
    return Dataset.objects.create(
        owner=owner, name=name, file_path=str(path),
        size_bytes=path.stat().st_size, rows=30, columns=2)


def make_run(owner, dataset, status=Run.Status.QUEUED):
    return Run.objects.create(
        owner=owner, dataset=dataset, target_column='label', model_name='logistic_regression',
        params_json={}, preprocessing_json={'missing': 'median', 'categorical': 'one_hot'},
        split_json={'test_size': 0.2, 'random_state': 42}, status=status)


@pytest.fixture
def alice(db):                                   # the owner of the items
    return make_user('alice_owner', Role.STUDENT)


@pytest.fixture
def bob(db):                                     # another ordinary user
    return make_user('bob_other', Role.DATA_SCIENTIST)


@pytest.fixture
def admin_user(db):
    return make_user('root_admin', Role.ADMIN)


@pytest.fixture
def alice_dataset(alice, tmp_path):
    return make_dataset(alice, tmp_path)


@pytest.fixture
def alice_run(alice, alice_dataset):
    return make_run(alice, alice_dataset)


@pytest.fixture(autouse=True)
def clean_log(db):
    """Fixtures above log events too (logins, uploads); tests look at what happens after."""
    from audit.models import AuditLog

    yield
    AuditLog.objects.all().delete()
