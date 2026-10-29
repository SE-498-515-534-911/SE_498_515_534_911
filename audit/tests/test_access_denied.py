"""US-38: refused requests are logged (MLE-SR-005; TC-SEC-01 steps 1, 2 and 4)."""
import json

import pytest

from audit.models import Action, AuditLog

pytestmark = pytest.mark.django_db


def denied():
    return list(AuditLog.objects.filter(action=Action.ACCESS_DENIED))


@pytest.fixture
def start_clean():
    """Forget entries written while the fixtures were set up."""
    AuditLog.objects.all().delete()


def post_json(client, url, payload):
    return client.post(url, json.dumps(payload), content_type='application/json')


# ---- roles: 403 -------------------------------------------------------------------------

def test_a_student_opening_an_admin_page_is_logged(client, alice, start_clean):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    assert client.get('/accounts/admin-dashboard/').status_code == 403
    entry = denied()[0]
    assert entry.user == alice
    assert entry.target == 'GET /accounts/admin-dashboard/'
    assert entry.ip_address == '127.0.0.1'


def test_a_student_opening_the_django_admin_site_is_logged(client, alice):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    assert client.get('/admin/').status_code == 403
    assert [e.user for e in denied()] == [alice]


def test_an_admin_using_a_data_feature_is_logged(client, admin_user, alice_dataset):
    client.force_login(admin_user)
    AuditLog.objects.all().delete()
    response = post_json(client, '/api/train', {'dataset_id': alice_dataset.pk,
                                                'target_column': 'label', 'model': 'knn'})
    assert response.status_code == 403
    assert [e.user for e in denied()] == [admin_user]


def test_a_page_that_is_allowed_leaves_no_denial(client, alice):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    assert client.get('/accounts/').status_code == 200
    assert denied() == []


def test_a_visitor_who_is_not_logged_in_is_not_logged_as_denied(client, db):
    assert client.get('/accounts/admin-dashboard/').status_code == 302
    assert client.get('/api/runs').status_code == 401
    assert denied() == []


def test_the_query_string_is_never_logged(client, alice):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    client.get('/accounts/admin-dashboard/?token=very-secret-value')
    assert 'very-secret-value' not in denied()[0].target


# ---- ownership: someone else's item looks like a missing one (404) ----------------------

@pytest.mark.parametrize('url', ['/api/train/{id}', '/api/evaluate/{id}', '/runs/{id}/results/'])
def test_asking_for_someone_elses_run_is_logged_with_the_run_id(client, bob, alice_run, url):
    client.force_login(bob)
    AuditLog.objects.all().delete()
    response = client.get(url.format(id=alice_run.pk))
    assert response.status_code == 404                       # the user is just told "not found"
    entry = denied()[0]
    assert entry.user == bob and entry.target == f'run:{alice_run.pk}'


def test_asking_for_a_run_that_does_not_exist_is_not_logged(client, bob, alice_run):
    client.force_login(bob)
    AuditLog.objects.all().delete()
    assert client.get('/api/train/999999').status_code == 404
    assert denied() == []


def test_asking_for_your_own_run_is_not_logged(client, alice, alice_run):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    assert client.get(f'/api/train/{alice_run.pk}').status_code == 200
    assert denied() == []


def test_training_on_someone_elses_dataset_is_logged(client, bob, alice_dataset):
    client.force_login(bob)
    AuditLog.objects.all().delete()
    response = post_json(client, '/api/train', {'dataset_id': alice_dataset.pk,
                                                'target_column': 'label', 'model': 'knn'})
    assert response.status_code == 404
    entry = denied()[0]
    assert entry.user == bob and entry.target == f'dataset:{alice_dataset.pk}'


def test_preprocessing_someone_elses_dataset_is_logged(client, bob, alice_dataset):
    client.force_login(bob)
    AuditLog.objects.all().delete()
    response = client.post('/api/datasets/preprocess',
                           {'dataset_id': alice_dataset.pk, 'strategy': 'drop_missing'})
    assert response.status_code == 404
    assert [e.target for e in denied()] == [f'dataset:{alice_dataset.pk}']


def test_a_dataset_that_does_not_exist_is_not_logged(client, bob, db):
    client.force_login(bob)
    AuditLog.objects.all().delete()
    response = post_json(client, '/api/train', {'dataset_id': 999999,
                                                'target_column': 'label', 'model': 'knn'})
    assert response.status_code == 404
    assert denied() == []


@pytest.mark.parametrize('bad_id', ['abc', '', None, True, [1], {'a': 1}, 10 ** 30])
def test_odd_dataset_ids_never_break_the_response(client, bob, bad_id):
    client.force_login(bob)
    response = post_json(client, '/api/train', {'dataset_id': bad_id,
                                                'target_column': 'label', 'model': 'knn'})
    assert response.status_code in (400, 404)


def test_malformed_json_never_breaks_the_response(client, bob):
    client.force_login(bob)
    response = client.post('/api/train', '{not json', content_type='application/json')
    assert response.status_code == 400
