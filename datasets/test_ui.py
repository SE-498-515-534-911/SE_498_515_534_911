import pytest
from accounts.models import Profile, Role
from datasets.models import Dataset

pytestmark = pytest.mark.django_db


@pytest.fixture
def ui_student(django_user_model):
    user = django_user_model.objects.create_user(
        username="ui_student", password="Test-password-123"
    )
    Profile.objects.update_or_create(
        user=user, defaults={"role": Role.STUDENT}
    )
    return user


def test_dashboard_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


def test_dashboard_shows_user_dataset_count(client, ui_student):
    other = type(ui_student).objects.create_user(
        username="another_student", password="Test-password-123"
    )
    Profile.objects.update_or_create(
        user=other, defaults={"role": Role.STUDENT}
    )
    Dataset.objects.create(
        owner=ui_student, name="mine.csv", file_path="/tmp/mine.csv",
        size_bytes=24, rows=4, columns=2,
        profile_json={"preview": [], "columns": []},
    )
    Dataset.objects.create(
        owner=other, name="not-mine.csv", file_path="/tmp/other.csv",
        size_bytes=24, rows=4, columns=2,
        profile_json={"preview": [], "columns": []},
    )
    client.force_login(ui_student)

    response = client.get("/")

    assert response.status_code == 200
    assert response.context["dataset_count"] == 1
    assert b"mine.csv" in response.content
    assert b"not-mine.csv" not in response.content


def test_dataset_workspace_renders_for_student(client, ui_student):
    client.force_login(ui_student)
    response = client.get("/datasets/")
    assert response.status_code == 200
    assert b"Upload a dataset" in response.content
    assert b"Preprocess data" in response.content


def test_dataset_workspace_rejects_admin(client, django_user_model):
    admin = django_user_model.objects.create_user(
        username="ui_admin", password="Test-password-123"
    )
    Profile.objects.update_or_create(
        user=admin, defaults={"role": Role.ADMIN}
    )
    client.force_login(admin)
    response = client.get("/datasets/")
    assert response.status_code == 403


def test_workspace_contains_supported_strategies(client, ui_student):
    client.force_login(ui_student)
    response = client.get("/datasets/")
    for strategy in (b"mean", b"median", b"most_frequent", b"drop_rows"):
        assert strategy in response.content
