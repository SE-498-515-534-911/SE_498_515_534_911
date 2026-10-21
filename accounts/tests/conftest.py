import pytest
from django.contrib.auth import get_user_model

from accounts.models import Role

User = get_user_model()


def _make_user(username, role):
    user = User.objects.create_user(username, f'{username}@example.com', 'Passw0rd1')
    user.profile.role = role
    user.profile.save()
    return user


@pytest.fixture
def student(db):
    return _make_user('student_u', Role.STUDENT)


@pytest.fixture
def scientist(db):
    return _make_user('scientist_u', Role.DATA_SCIENTIST)


@pytest.fixture
def admin_user(db):
    return _make_user('admin_u', Role.ADMIN)
