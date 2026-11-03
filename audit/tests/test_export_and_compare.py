"""US-38: exports are logged, and compare attempts on other people's runs are logged as denied
(MLE-SR-005; SAD 4.4.4: REPORT_EXPORT, ACCESS_DENIED; TC-SEC-01)."""
import json

import pytest

from audit.models import Action, AuditLog

from .conftest import make_dataset, make_run

pytestmark = pytest.mark.django_db

COMPARE = '/api/runs/compare'


def entries(action):
    return list(AuditLog.objects.filter(action=action))


def compare(client, run_ids):
    return client.post(COMPARE, json.dumps({'run_ids': run_ids}), content_type='application/json')


@pytest.fixture
def two_runs(alice, alice_dataset):
    return make_run(alice, alice_dataset), make_run(alice, alice_dataset)


# ---- REPORT_EXPORT --------------------------------------------------------------------

def test_exporting_your_own_run_is_logged(client, alice, alice_run):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    response = client.get(f'/api/runs/{alice_run.pk}/export')
    assert response.status_code == 200 and response['Content-Type'].startswith('text/csv')
    entry = entries(Action.REPORT_EXPORT)[0]
    assert entry.user == alice
    assert entry.target == f'run:{alice_run.pk}'
    assert entry.ip_address == '127.0.0.1'


def test_the_exported_report_is_not_copied_into_the_log(client, alice, alice_run):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    client.get(f'/api/runs/{alice_run.pk}/export')
    stored = json.dumps(list(AuditLog.objects.values()), default=str)
    assert 'logistic_regression' not in stored and 'data.csv' not in stored and 'label' not in stored


def test_exporting_someone_elses_run_is_refused_logged_as_denied_and_not_as_an_export(
        client, bob, alice_run):
    client.force_login(bob)
    AuditLog.objects.all().delete()
    assert client.get(f'/api/runs/{alice_run.pk}/export').status_code == 404
    assert entries(Action.REPORT_EXPORT) == []
    assert [e.target for e in entries(Action.ACCESS_DENIED)] == [f'run:{alice_run.pk}']


def test_exporting_a_run_that_does_not_exist_logs_nothing(client, bob):
    client.force_login(bob)
    AuditLog.objects.all().delete()
    assert client.get('/api/runs/999999/export').status_code == 404
    assert AuditLog.objects.count() == 0


def test_the_admin_cannot_export_and_nothing_is_logged_as_an_export(client, admin_user, alice_run):
    client.force_login(admin_user)
    AuditLog.objects.all().delete()
    assert client.get(f'/api/runs/{alice_run.pk}/export').status_code == 403
    assert entries(Action.REPORT_EXPORT) == []
    assert len(entries(Action.ACCESS_DENIED)) == 1


# ---- compare: other people's runs ------------------------------------------------------

def test_comparing_your_own_runs_leaves_no_denial(client, alice, two_runs):
    client.force_login(alice)
    AuditLog.objects.all().delete()
    assert compare(client, [r.pk for r in two_runs]).status_code == 200
    assert entries(Action.ACCESS_DENIED) == []


def test_comparing_with_someone_elses_run_is_404_and_logged_with_that_run(
        client, alice, bob, alice_run, tmp_path):
    bobs_run = make_run(bob, make_dataset(bob, tmp_path, name='bobs.csv'))
    client.force_login(bob)
    AuditLog.objects.all().delete()
    response = compare(client, [bobs_run.pk, alice_run.pk])
    assert response.status_code == 404
    entry = entries(Action.ACCESS_DENIED)[0]
    assert entry.user == bob and entry.target == f'run:{alice_run.pk}'


def test_the_refusal_does_not_reveal_that_the_run_exists(client, bob, alice_run, tmp_path):
    bobs_run = make_run(bob, make_dataset(bob, tmp_path, name='bobs.csv'))
    client.force_login(bob)
    theirs = compare(client, [bobs_run.pk, alice_run.pk])
    missing = compare(client, [bobs_run.pk, 999999])
    assert theirs.status_code == missing.status_code == 404
    assert theirs.json()['error']['message'] == missing.json()['error']['message']


def test_comparing_runs_that_do_not_exist_is_not_logged(client, bob):
    client.force_login(bob)
    AuditLog.objects.all().delete()
    assert compare(client, [999998, 999999]).status_code == 404
    assert entries(Action.ACCESS_DENIED) == []


@pytest.mark.parametrize('run_ids', ['abc', [1, 'x'], [[1], [2]], [True, False],
                                     {'a': 1}, None, [], [1]])
def test_odd_run_ids_never_break_the_response(client, bob, run_ids):
    client.force_login(bob)
    assert compare(client, run_ids).status_code in (400, 404)


def test_malformed_json_never_breaks_the_response(client, bob):
    client.force_login(bob)
    response = client.post(COMPARE, '{broken', content_type='application/json')
    assert response.status_code == 400


def test_the_audit_check_itself_copes_with_huge_run_ids(bob):
    """The compare endpoint has its own problem with numbers this large (it answers 500),
    so this checks only that the audit middleware does not add a failure of its own."""
    from django.test import RequestFactory
    from django.urls import resolve

    from audit.middleware import _foreign_item

    request = RequestFactory().post(
        COMPARE, json.dumps({'run_ids': [10 ** 30, 10 ** 31]}), content_type='application/json')
    request.resolver_match = resolve(COMPARE)
    assert _foreign_item(request, bob) == ''
