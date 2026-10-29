"""US-37: GET /api/admin/audit (MLE-F-016, MLE-SR-005; SAD 4.3.2, 4.4.4)."""
import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from audit import services
from audit.models import Action, AuditLog

pytestmark = pytest.mark.django_db

User = get_user_model()
URL = '/api/admin/audit'


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    AuditLog.objects.all().delete()          # start from an empty log; the fixtures logged a login
    return client


def log(action, user=None, target='', minutes_ago=0):
    services.record(action, user=user, target=target)
    entry = AuditLog.objects.latest('id')
    # entries cannot be edited through save(), so move the time with a queryset update
    AuditLog.objects.filter(pk=entry.pk).update(timestamp=timezone.now() - timedelta(minutes=minutes_ago))
    return entry


def get(client, query=''):
    return client.get(URL + query)


# ---- content ------------------------------------------------------------------------------

def test_entries_show_time_user_action_target_and_address(admin_client, student):
    services.record(Action.UPLOAD, user=student, target='dataset:7')
    AuditLog.objects.update(ip_address='203.0.113.9')
    entry = get(admin_client).json()['entries'][0]
    assert entry['user'] == {'id': student.pk, 'username': 'student_u'}
    assert entry['action'] == 'UPLOAD' and entry['target'] == 'dataset:7'
    assert entry['ip_address'] == '203.0.113.9'
    assert entry['timestamp'].endswith('Z')


def test_the_newest_entry_comes_first(admin_client, student):
    log(Action.REGISTER, student, 'user:1', minutes_ago=30)
    log(Action.LOGOUT, student, minutes_ago=0)
    log(Action.UPLOAD, student, 'dataset:1', minutes_ago=10)
    actions = [e['action'] for e in get(admin_client).json()['entries']]
    assert actions == ['LOGOUT', 'UPLOAD', 'REGISTER']


def test_an_entry_with_no_known_user_shows_user_null(admin_client):
    services.record(Action.LOGIN_FAILED)
    assert get(admin_client).json()['entries'][0]['user'] is None


def test_actions_taken_through_the_admin_api_appear_in_the_log(admin_client, student):
    admin_client.patch(f'/api/admin/users/{student.pk}', json.dumps({'role': 'DATA_SCIENTIST'}),
                       content_type='application/json')
    entry = get(admin_client).json()['entries'][0]
    assert entry['action'] == 'ADMIN_USER_UPDATE'
    assert entry['target'] == f'user:{student.pk} role->DATA_SCIENTIST'
    assert entry['user']['username'] == 'admin_u'


def test_the_log_shows_no_raw_data_and_no_credentials(admin_client, student):
    services.record(Action.UPLOAD, user=student, target='dataset:7')
    text = get(admin_client).content.decode()
    assert 'password' not in text.lower() and 'pbkdf2' not in text and '@example.com' not in text


def test_reading_the_log_does_not_add_entries(admin_client):
    services.record(Action.LOGOUT)
    before = AuditLog.objects.count()
    get(admin_client)
    get(admin_client)
    assert AuditLog.objects.count() == before


# ---- filters ----------------------------------------------------------------------------------

def test_filter_by_action(admin_client, student):
    log(Action.LOGIN_FAILED, student)
    log(Action.UPLOAD, student, 'dataset:1')
    log(Action.LOGIN_FAILED, None)
    entries = get(admin_client, '?action=LOGIN_FAILED').json()['entries']
    assert [e['action'] for e in entries] == ['LOGIN_FAILED', 'LOGIN_FAILED']


def test_filter_by_user(admin_client, student, scientist):
    log(Action.UPLOAD, student, 'dataset:1')
    log(Action.UPLOAD, scientist, 'dataset:2')
    entries = get(admin_client, f'?user_id={scientist.pk}').json()['entries']
    assert [e['target'] for e in entries] == ['dataset:2']


def test_filters_combine(admin_client, student):
    log(Action.UPLOAD, student, 'dataset:1')
    log(Action.LOGOUT, student)
    entries = get(admin_client, f'?action=UPLOAD&user_id={student.pk}').json()['entries']
    assert len(entries) == 1


@pytest.mark.parametrize('query,field', [('?action=HACK', 'action'), ('?action=upload', 'action'),
                                         ('?user_id=abc', 'user_id')])
def test_unknown_filter_values_are_400(admin_client, query, field):
    response = get(admin_client, query)
    assert response.status_code == 400
    assert response.json()['error']['details']['field'] == field


# ---- paging ---------------------------------------------------------------------------------------

def test_the_log_is_paged(admin_client, student):
    AuditLog.objects.bulk_create([AuditLog(action=Action.LOGOUT, target=f'n{i}') for i in range(45)])
    data = get(admin_client).json()
    assert len(data['entries']) == 20
    assert data['pagination'] == {'page': 1, 'page_size': 20, 'total': 45, 'pages': 3}
    assert len(get(admin_client, '?page=3').json()['entries']) == 5
    assert get(admin_client, '?page_size=101').status_code == 400


def test_the_list_does_not_query_once_per_entry(admin_client, student, django_assert_max_num_queries):
    for i in range(30):
        services.record(Action.UPLOAD, user=student, target=f'dataset:{i}')
    with django_assert_max_num_queries(8):
        assert get(admin_client, '?page_size=30').status_code == 200


# ---- who may read ------------------------------------------------------------------------------------

@pytest.mark.parametrize('fixture', ['student', 'scientist'])
def test_other_roles_cannot_read_the_log(client, request, fixture):
    user = request.getfixturevalue(fixture)
    services.record(Action.UPLOAD, user=user, target='dataset:1')
    client.force_login(user)
    response = client.get(URL)
    assert response.status_code == 403 and 'entries' not in response.json()


def test_a_visitor_cannot_read_the_log(client, db):
    assert client.get(URL).status_code == 401


def test_the_log_cannot_be_written_through_the_api(admin_client):
    for method in ('post', 'put', 'patch', 'delete'):
        assert getattr(admin_client, method)(URL).status_code == 405


def test_a_refused_attempt_to_read_the_log_is_itself_logged(client, student):
    client.force_login(student)
    AuditLog.objects.all().delete()
    client.get(URL)
    entry = AuditLog.objects.get(action=Action.ACCESS_DENIED)
    assert entry.user == student and entry.target == f'GET {URL}'
