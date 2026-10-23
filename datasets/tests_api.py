
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Profile, Role


pytestmark = pytest.mark.django_db


@pytest.fixture
def student(django_user_model):
    user = django_user_model.objects.create_user(
        username="dataset_student",
        password="test-password",
    )
    profile, _ = Profile.objects.get_or_create(
        user=user,
        defaults={"role": Role.STUDENT},
    )
    profile.role = Role.STUDENT
    profile.save()
    return user


def make_csv():
    return SimpleUploadedFile(
        "sample.csv",
        b"age,city\n20,Chennai\n,Delhi\n30,\n",
        content_type="text/csv",
    )


def test_preprocess_endpoint_success(client, student):
    client.force_login(student)

    response = client.post(
        "/api/datasets/preprocess",
        {"file": make_csv(), "strategy": "mean"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Dataset preprocessing completed."
    assert body["strategy"] == "mean"
    assert body["rows"] == 3
    assert "age" in body["columns"]
    assert any(column.startswith("city_") for column in body["columns"])
    assert len(body["data"]) == 3


def test_preprocess_endpoint_rejects_missing_file(client, student):
    client.force_login(student)

    response = client.post(
        "/api/datasets/preprocess",
        {"strategy": "mean"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_preprocess_endpoint_rejects_non_csv(client, student):
    client.force_login(student)

    uploaded = SimpleUploadedFile(
        "sample.txt",
        b"not a csv",
        content_type="text/plain",
    )
    response = client.post(
        "/api/datasets/preprocess",
        {"file": uploaded, "strategy": "mean"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_preprocess_endpoint_rejects_invalid_strategy(client, student):
    client.force_login(student)

    response = client.post(
        "/api/datasets/preprocess",
        {"file": make_csv(), "strategy": "unknown"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_preprocess_endpoint_rejects_admin(client, admin_user):
    client.force_login(admin_user)

    response = client.post(
        "/api/datasets/preprocess",
        {"file": make_csv(), "strategy": "mean"},
    )

    assert response.status_code == 403


def test_preprocess_endpoint_requires_login(client):
    response = client.post(
        "/api/datasets/preprocess",
        {"file": make_csv(), "strategy": "mean"},
    )

    assert response.status_code in (302, 403)
