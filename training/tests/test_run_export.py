import csv
import io

import pytest

from experiments.models import Metric, Run


pytestmark = pytest.mark.django_db


def create_run(owner, dataset):
    return Run.objects.create(
        owner=owner,
        dataset=dataset,
        target_column="label",
        model_name="random_forest",
        params_json={"n_estimators": 100},
        preprocessing_json={"missing": "median"},
        split_json={"test_size": 0.2, "random_state": 42},
        status=Run.Status.COMPLETED,
    )


def test_export_run_csv_contains_settings_and_metrics(student_client, student, dataset):
    run = create_run(student, dataset)
    Metric.objects.create(run=run, name="accuracy", value=0.95)

    response = student_client.get(f"/api/runs/{run.id}/export")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert f'run-{run.id}-results.csv' in response["Content-Disposition"]

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))

    assert ["run_id", str(run.id)] in rows
    assert ["model", "random_forest"] in rows
    assert ["target_column", "label"] in rows
    assert ["Metric", "Value"] in rows
    assert ["accuracy", "0.95"] in rows
    assert ["dataset_id", str(dataset.id)] in rows
    assert ["dataset_name", dataset.name] in rows
    assert ["status", Run.Status.COMPLETED] in rows
    assert ['parameters', '{"n_estimators": 100}'] in rows
    assert ['preprocessing', '{"missing": "median"}'] in rows
    assert ['split', '{"random_state": 42, "test_size": 0.2}'] in rows



@pytest.mark.parametrize("dangerous_value", ["=1+1", "+1+1", "-1+1", "@SUM(A1:A2)"])
def test_export_neutralises_formula_injection(
    student_client, student, dataset, dangerous_value
):
    run = create_run(student, dataset)
    run.target_column = dangerous_value
    run.save(update_fields=["target_column"])

    response = student_client.get(f"/api/runs/{run.id}/export")

    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))

    assert ["target_column", f"'{dangerous_value}"] in rows

@pytest.mark.parametrize(
    "dangerous_value",
    [
        " =1+1",
        "\t=1+1",
        "\r=1+1",
        "\n=1+1",
        " +1+1",
        " @SUM(A1:A2)",
    ],
)
def test_export_neutralises_formula_after_whitespace(
    student_client, student, dataset, dangerous_value
):
    run = create_run(student, dataset)
    run.target_column = dangerous_value
    run.save(update_fields=["target_column"])

    response = student_client.get(f"/api/runs/{run.id}/export")

    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))

    assert ["target_column", f"'{dangerous_value}"] in rows


def test_export_preserves_negative_numeric_metric(student_client, student, dataset):
    run = create_run(student, dataset)
    Metric.objects.create(run=run, name="loss", value=-0.25)

    response = student_client.get(f"/api/runs/{run.id}/export")

    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))

    assert ["loss", "-0.25"] in rows

def test_export_neutralises_formula_injection_in_metric_name(
    student_client, student, dataset
):
    run = create_run(student, dataset)
    Metric.objects.create(run=run, name="=HYPERLINK('https://example.com')", value=0.95)

    response = student_client.get(f"/api/runs/{run.id}/export")

    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))

    assert ["'=HYPERLINK('https://example.com')", "0.95"] in rows


def test_export_returns_404_for_another_users_run(student_client, bob, dataset):
    run = create_run(bob, dataset)

    response = student_client.get(f"/api/runs/{run.id}/export")

    assert response.status_code == 404


def test_export_requires_authentication(client, student, dataset):
    run = create_run(student, dataset)

    response = client.get(f"/api/runs/{run.id}/export")

    assert response.status_code == 401


def test_export_rejects_admin(client, admin_user, dataset):
    run = create_run(admin_user, dataset)
    client.force_login(admin_user)

    response = client.get(f"/api/runs/{run.id}/export")

    assert response.status_code == 403


def test_export_rejects_post(student_client, student, dataset):
    run = create_run(student, dataset)

    response = student_client.post(f"/api/runs/{run.id}/export")

    assert response.status_code == 405
