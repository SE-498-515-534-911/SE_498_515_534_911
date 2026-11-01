import pytest
from django.urls import reverse

from accounts.models import Role
from evaluation.tests.conftest import make_user, train_run

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def temporary_storage(settings, tmp_path):
    settings.MODEL_ARTIFACT_ROOT = tmp_path / "artifacts"
    settings.DATA_ROOT = tmp_path / "data"
    settings.TRAINING_JOBS_INLINE = True


@pytest.fixture
def student(db):
    return make_user("exp_student", Role.STUDENT)


@pytest.fixture
def scientist(db):
    return make_user("exp_scientist", Role.DATA_SCIENTIST)


@pytest.fixture
def admin_user(db):
    return make_user("exp_admin", Role.ADMIN)


@pytest.fixture
def other_user(db):
    return make_user("exp_other", Role.STUDENT)


def page(client):
    return client.get(reverse("experiments"))


def test_anonymous_user_is_redirected_to_login(client):
    response = page(client)

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


def test_admin_is_forbidden(client, admin_user):
    client.force_login(admin_user)

    assert page(client).status_code == 403


@pytest.mark.parametrize("fixture", ["student", "scientist"])
def test_data_user_can_access_experiments(client, request, fixture):
    user = request.getfixturevalue(fixture)
    client.force_login(user)

    response = page(client)

    assert response.status_code == 200
    assert "Experiments" in response.content.decode()


def test_user_sees_only_their_own_runs(client, student, other_user):
    own_run = train_run(student)
    other_run = train_run(other_user)

    client.force_login(student)
    response = page(client)

    assert response.status_code == 200
    html = response.content.decode()

    assert f"#{own_run.pk}" in html
    assert f"#{other_run.pk}" not in html


def test_empty_experiments_page(client, student):
    client.force_login(student)

    response = page(client)

    assert response.status_code == 200
    assert b"No experiments yet" in response.content