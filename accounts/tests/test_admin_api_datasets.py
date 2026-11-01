"""US-37: GET /api/admin/datasets and DELETE /api/admin/datasets/<id> (MLE-F-016; SAD 4.3.2, DD5)."""
import json
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from sklearn.linear_model import LogisticRegression

from audit.models import Action, AuditLog
from datasets.models import Dataset
from experiments.models import Metric, Run
from training.artifacts import save_artifact, user_artifact_dir
from training.models import ModelArtifact

pytestmark = pytest.mark.django_db

User = get_user_model()
LIST_URL = '/api/admin/datasets'
SECRET = 'SECRET_CELL_VALUE_4711'


@pytest.fixture(autouse=True)
def storage(settings, tmp_path):
    settings.DATA_ROOT = tmp_path / 'data'
    settings.MODEL_ARTIFACT_ROOT = tmp_path / 'artifacts'


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


def make_dataset(owner, name='data.csv'):
    from django.conf import settings
    folder = Path(settings.DATA_ROOT) / str(owner.pk) / 'datasets'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{name}.stored'
    path.write_text(f'x,label\n{SECRET},1\n2,0\n', encoding='utf-8')
    return Dataset.objects.create(owner=owner, name=name, file_path=str(path),
                                  size_bytes=path.stat().st_size, rows=2, columns=2,
                                  profile_json=[{'column': 'x', 'unique': 2}])


def make_run(owner, dataset, status=Run.Status.COMPLETED, with_model=True):
    artifact = save_artifact(owner, LogisticRegression()) if with_model else None
    run = Run.objects.create(owner=owner, dataset=dataset, target_column='label',
                             model_name='logistic_regression', status=status, artifact=artifact)
    Metric.objects.create(run=run, name='test_accuracy', value=0.9)
    return run


def delete(client, dataset):
    return client.delete(f'/api/admin/datasets/{dataset.pk}')


# ============================== LIST ======================================================

def test_the_admin_lists_name_owner_size_and_upload_date(admin_client, student):
    dataset = make_dataset(student, 'iris.csv')
    data = admin_client.get(LIST_URL).json()
    assert data['datasets'] == [{
        'id': dataset.pk,
        'name': 'iris.csv',
        'owner': {'id': student.pk, 'username': 'student_u'},
        'size_bytes': dataset.size_bytes,
        'uploaded_at': data['datasets'][0]['uploaded_at'],
    }]
    assert data['datasets'][0]['uploaded_at'].endswith('Z')


def test_datasets_of_every_user_are_listed_newest_first(admin_client, student, scientist):
    first = make_dataset(student, 'one.csv')
    second = make_dataset(scientist, 'two.csv')
    ids = [d['id'] for d in admin_client.get(LIST_URL).json()['datasets']]
    assert ids == [second.pk, first.pk]


def test_the_admin_never_sees_the_contents_or_the_path(admin_client, student):
    dataset = make_dataset(student)
    response = admin_client.get(LIST_URL)
    text = response.content.decode()
    assert SECRET not in text                       # no cell value
    assert dataset.file_path not in text and '.stored' not in text
    assert 'profile' not in text and '"rows"' not in text and '"columns"' not in text


def test_there_is_no_endpoint_to_read_one_datasets_contents(admin_client, student):
    dataset = make_dataset(student)
    response = admin_client.get(f'/api/admin/datasets/{dataset.pk}')
    assert response.status_code == 405
    assert SECRET not in response.content.decode()


def test_the_list_is_paged(admin_client, student):
    Dataset.objects.bulk_create([
        Dataset(owner=student, name=f'd{i}.csv', file_path='x', size_bytes=1, rows=1, columns=1)
        for i in range(25)])
    data = admin_client.get(LIST_URL).json()
    assert len(data['datasets']) == 20
    assert data['pagination'] == {'page': 1, 'page_size': 20, 'total': 25, 'pages': 2}
    assert len(admin_client.get(LIST_URL + '?page=2').json()['datasets']) == 5
    assert admin_client.get(LIST_URL + '?page_size=500').status_code == 400


@pytest.mark.parametrize('fixture', ['student', 'scientist'])
def test_other_roles_cannot_list_datasets(client, request, fixture):
    user = request.getfixturevalue(fixture)
    make_dataset(user)
    client.force_login(user)
    response = client.get(LIST_URL)
    assert response.status_code == 403 and 'datasets' not in response.json()


def test_a_visitor_cannot_list_datasets(client, db):
    assert client.get(LIST_URL).status_code == 401


# ============================== DELETE ====================================================

def test_the_admin_deletes_any_users_dataset_and_its_file(admin_client, student):
    dataset = make_dataset(student)
    file = Path(dataset.file_path)
    assert file.exists()
    assert delete(admin_client, dataset).status_code == 204
    assert not Dataset.objects.filter(pk=dataset.pk).exists()
    assert not file.exists()


def test_the_runs_metrics_and_model_files_of_the_dataset_go_too(admin_client, student):
    dataset = make_dataset(student)
    run = make_run(student, dataset)
    model_file = user_artifact_dir(student) / run.artifact.file_name
    assert model_file.exists()

    delete(admin_client, dataset)

    assert not Run.objects.filter(pk=run.pk).exists()
    assert not Metric.objects.filter(run_id=run.pk).exists()
    assert not ModelArtifact.objects.exists()
    assert not model_file.exists()


def test_other_datasets_and_their_files_are_untouched(admin_client, student, scientist):
    doomed = make_dataset(student, 'doomed.csv')
    kept = make_dataset(scientist, 'kept.csv')
    kept_run = make_run(scientist, kept)
    kept_model = user_artifact_dir(scientist) / kept_run.artifact.file_name

    delete(admin_client, doomed)

    assert Dataset.objects.filter(pk=kept.pk).exists() and Path(kept.file_path).exists()
    assert Run.objects.filter(pk=kept_run.pk).exists() and kept_model.exists()


def test_a_dataset_in_use_by_a_training_job_is_refused_and_left_alone(admin_client, student):
    dataset = make_dataset(student)
    make_run(student, dataset, status=Run.Status.RUNNING, with_model=False)
    response = delete(admin_client, dataset)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'UNPROCESSABLE'
    assert Dataset.objects.filter(pk=dataset.pk).exists() and Path(dataset.file_path).exists()
    assert not AuditLog.objects.filter(action=Action.ADMIN_DATASET_DELETE).exists()


def test_finished_runs_do_not_block_deletion(admin_client, student):
    dataset = make_dataset(student)
    make_run(student, dataset, status=Run.Status.FAILED, with_model=False)
    assert delete(admin_client, dataset).status_code == 204


def test_a_dataset_whose_file_is_already_gone_is_still_removed(admin_client, student):
    dataset = make_dataset(student)
    Path(dataset.file_path).unlink()
    assert delete(admin_client, dataset).status_code == 204
    assert not Dataset.objects.filter(pk=dataset.pk).exists()


def test_a_record_pointing_outside_the_data_folder_never_deletes_that_file(
        admin_client, student, tmp_path):
    """A damaged row must not let this endpoint delete an arbitrary file."""
    outside = tmp_path / 'important.txt'
    outside.write_text('keep me')
    dataset = Dataset.objects.create(owner=student, name='bad.csv', file_path=str(outside),
                                     size_bytes=1, rows=1, columns=1)
    assert delete(admin_client, dataset).status_code == 204
    assert not Dataset.objects.filter(pk=dataset.pk).exists()      # the record is removed
    assert outside.exists()                                        # the file is not


def test_a_path_with_dot_dot_cannot_escape_either(admin_client, student, tmp_path, settings):
    outside = tmp_path / 'secret.txt'
    outside.write_text('keep me')
    sneaky = Path(settings.DATA_ROOT) / '..' / 'secret.txt'
    dataset = Dataset.objects.create(owner=student, name='sneaky.csv', file_path=str(sneaky),
                                     size_bytes=1, rows=1, columns=1)
    delete(admin_client, dataset)
    assert outside.exists()


def test_an_unknown_dataset_is_404(admin_client, db):
    response = admin_client.delete('/api/admin/datasets/999999')
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'NOT_FOUND'


def test_deleting_twice_the_second_time_is_404(admin_client, student):
    dataset = make_dataset(student)
    pk = dataset.pk
    assert delete(admin_client, dataset).status_code == 204
    assert admin_client.delete(f'/api/admin/datasets/{pk}').status_code == 404


# ---- the audit log (MLE-SR-005) ------------------------------------------------------------

def test_the_deletion_is_logged_with_admin_dataset_and_owner(admin_client, admin_user, student):
    dataset = make_dataset(student, 'private_name.csv')
    pk = dataset.pk
    delete(admin_client, dataset)
    entry = AuditLog.objects.get(action=Action.ADMIN_DATASET_DELETE)
    assert entry.user == admin_user
    assert entry.target == f'dataset:{pk} owner:{student.pk}'
    assert entry.ip_address == '127.0.0.1'
    stored = json.dumps(list(AuditLog.objects.values()), default=str)
    assert 'private_name' not in stored and SECRET not in stored


# ---- who may delete --------------------------------------------------------------------------

@pytest.mark.parametrize('fixture', ['student', 'scientist'])
def test_other_roles_cannot_delete_even_their_own_dataset_here(client, request, fixture):
    user = request.getfixturevalue(fixture)
    dataset = make_dataset(user)
    client.force_login(user)
    assert delete(client, dataset).status_code == 403
    assert Dataset.objects.filter(pk=dataset.pk).exists() and Path(dataset.file_path).exists()


def test_a_visitor_cannot_delete(client, student):
    dataset = make_dataset(student)
    assert delete(client, dataset).status_code == 401
    assert Dataset.objects.filter(pk=dataset.pk).exists()


def test_the_csrf_token_is_required_to_delete(admin_user, student):
    dataset = make_dataset(student)
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    assert delete(client, dataset).status_code == 403
    assert Dataset.objects.filter(pk=dataset.pk).exists()
