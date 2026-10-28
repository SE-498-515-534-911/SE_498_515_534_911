
import pytest

from experiments.models import Metric, Run


pytestmark = pytest.mark.django_db


def create_run(owner, dataset, *, model_name='random_forest', status='COMPLETED'):
    return Run.objects.create(
        owner=owner,
        dataset=dataset,
        target_column='label',
        model_name=model_name,
        params_json={},
        preprocessing_json={},
        split_json={'test_size': 0.2},
        status=status,
    )


def test_run_history_returns_only_owners_runs_newest_first(
    client, student, bob, dataset
):
    older = create_run(student, dataset, model_name='older_model')
    newer = create_run(student, dataset, model_name='newer_model')
    create_run(bob, dataset, model_name='other_user_model')

    client.force_login(student)
    response = client.get('/api/runs')

    assert response.status_code == 200
    runs = response.json()['runs']
    assert [item['run_id'] for item in runs][:2] == [newer.id, older.id]
    assert all(item['owner'] == student.id for item in runs)


def test_run_history_includes_run_details_and_metrics(
    client, student, dataset
):
    run = create_run(student, dataset)
    Metric.objects.create(run=run, name='accuracy', value=0.95)

    client.force_login(student)
    response = client.get('/api/runs')

    assert response.status_code == 200
    item = response.json()['runs'][0]
    assert item['dataset_id'] == dataset.id
    assert item['target_column'] == 'label'
    assert item['model'] == 'random_forest'
    assert item['split'] == {'test_size': 0.2}
    assert item['status'] == 'COMPLETED'
    assert item['metrics']['accuracy'] == pytest.approx(0.95)
    assert 'created_at' in item
    assert 'started_at' in item
    assert 'finished_at' in item


def test_run_history_requires_authentication(client):
    response = client.get('/api/runs')
    assert response.status_code == 401


def test_run_history_rejects_admin(client, admin_user):
    client.force_login(admin_user)
    response = client.get('/api/runs')
    assert response.status_code == 403

def create_run(
    owner, dataset, *, model_name='random_forest',
    status='COMPLETED', params=None
):
    return Run.objects.create(
        owner=owner,
        dataset=dataset,
        target_column='label',
        model_name=model_name,
        params_json=params or {},
        preprocessing_json={},
        split_json={'test_size': 0.2},
        status=status,
    )

def test_run_history_returns_empty_list_when_no_runs(client, student):
    client.force_login(student)

    response = client.get('/api/runs')

    assert response.status_code == 200
    assert response.json() == {'runs': []}


def test_run_history_rejects_post(client, student):
    client.force_login(student)

    response = client.post('/api/runs')

    assert response.status_code == 405


def test_run_history_includes_parameters(client, student, dataset):
    params = {'n_estimators': 100, 'max_depth': 5}
    create_run(student, dataset, params=params)

    client.force_login(student)
    response = client.get('/api/runs')

    assert response.status_code == 200
    assert response.json()['runs'][0]['params'] == params
