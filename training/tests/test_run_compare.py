import json

import pytest

from experiments.models import Metric, Run

pytestmark = pytest.mark.django_db


def create_comparison_run(owner, dataset, *, target_column="label",
                          model_name="random_forest", params=None):
    return Run.objects.create(
        owner=owner,
        dataset=dataset,
        target_column=target_column,
        model_name=model_name,
        params_json=params or {"n_estimators": 100},
        preprocessing_json={"missing": "median"},
        split_json={"test_size": 0.2},
        status=Run.Status.COMPLETED,
    )


def compare(client, run_ids):
    return client.post(
        "/api/runs/compare",
        data=json.dumps({"run_ids": run_ids}),
        content_type="application/json",
    )


def test_compare_two_runs_returns_configs_metrics_and_links(client, student, dataset):
    client.force_login(student)
    first = create_comparison_run(student, dataset, model_name="random_forest")
    second = create_comparison_run(
        student, dataset, model_name="logistic_regression",
        params={"C": 1.0},
    )
    Metric.objects.create(run=first, name="accuracy", value=0.91)
    Metric.objects.create(run=second, name="accuracy", value=0.87)

    response = compare(client, [first.pk, second.pk])

    assert response.status_code == 200
    body = response.json()
    assert body["dataset_id"] == dataset.pk
    assert body["target_column"] == "label"
    assert [run["run_id"] for run in body["runs"]] == [first.pk, second.pk]
    assert body["runs"][0]["metrics"]["accuracy"] == pytest.approx(0.91)
    assert body["runs"][1]["metrics"]["accuracy"] == pytest.approx(0.87)
    assert body["runs"][0]["model"] == "random_forest"
    assert body["runs"][1]["params"] == {"C": 1.0}
    assert body["runs"][0]["links"]["status"] == f"/api/train/{first.pk}"


@pytest.mark.parametrize("run_ids", [[], [1], [1, 2, 3, 4, 5], [1, 1], ["1", 2], [True, 2]])
def test_compare_rejects_invalid_run_id_lists(client, student, run_ids):
    client.force_login(student)
    response = compare(client, run_ids)
    assert response.status_code == 400


def test_compare_rejects_different_datasets(client, student, dataset, frame):
    from training.tests.conftest import store_dataset

    client.force_login(student)
    other_dataset = store_dataset(student, frame, name="other.csv")
    first = create_comparison_run(student, dataset)
    second = create_comparison_run(student, other_dataset)

    response = compare(client, [first.pk, second.pk])

    assert response.status_code == 400


def test_compare_rejects_different_targets(client, student, dataset):
    client.force_login(student)
    first = create_comparison_run(student, dataset, target_column="label")
    second = create_comparison_run(student, dataset, target_column="x1")

    response = compare(client, [first.pk, second.pk])

    assert response.status_code == 400


def test_compare_hides_runs_owned_by_another_user(client, student, bob, dataset):
    client.force_login(student)
    own_run = create_comparison_run(student, dataset)
    other_run = create_comparison_run(bob, dataset)

    response = compare(client, [own_run.pk, other_run.pk])

    assert response.status_code == 404


def test_compare_requires_authentication(client, student, dataset):
    first = create_comparison_run(student, dataset)
    second = create_comparison_run(student, dataset)

    response = compare(client, [first.pk, second.pk])

    assert response.status_code == 401


def test_compare_rejects_get(client, student):
    client.force_login(student)
    response = client.get("/api/runs/compare")
    assert response.status_code == 405
