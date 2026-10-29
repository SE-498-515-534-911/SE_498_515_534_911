"""US-37: GET /api/admin/users (MLE-F-016, MLE-F-002; SAD 4.3.2, 4.3.7)."""
import json

import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db

User = get_user_model()
URL = '/api/admin/users'


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


# ---- access (acceptance criterion: non-Admins are refused) ------------------------------

def test_a_student_is_refused(client, student):
    client.force_login(student)
    response = client.get(URL)
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'FORBIDDEN'


def test_a_data_scientist_is_refused(client, scientist):
    client.force_login(scientist)
    assert client.get(URL).status_code == 403


def test_a_visitor_gets_401(client, db):
    response = client.get(URL)
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'AUTH_REQUIRED'


def test_a_refused_request_returns_no_account_data(client, student):
    client.force_login(student)
    assert 'users' not in client.get(URL).json()


def test_post_is_not_allowed(admin_client):
    assert admin_client.post(URL).status_code == 405


# ---- what the Admin sees -----------------------------------------------------------------

def test_every_account_is_listed_with_role_and_status(admin_client, student, scientist, admin_user):
    data = admin_client.get(URL).json()
    by_name = {u['username']: u for u in data['users']}
    assert set(by_name) == {'student_u', 'scientist_u', 'admin_u'}
    assert by_name['student_u']['role'] == 'STUDENT'
    assert by_name['scientist_u']['role'] == 'DATA_SCIENTIST'
    assert by_name['admin_u']['role'] == 'ADMIN'
    assert all(u['is_active'] is True for u in by_name.values())
    assert set(by_name['student_u']) == {'id', 'username', 'role', 'is_active', 'date_joined', 'last_login'}


def test_accounts_are_listed_by_username(admin_client, student, scientist, admin_user):
    names = [u['username'] for u in admin_client.get(URL).json()['users']]
    assert names == sorted(names)


def test_a_deactivated_account_is_still_listed_and_marked(admin_client, student):
    student.is_active = False
    student.save()
    by_name = {u['username']: u for u in admin_client.get(URL).json()['users']}
    assert by_name['student_u']['is_active'] is False


def test_an_account_without_a_profile_shows_no_role(admin_client, student):
    student.profile.delete()
    by_name = {u['username']: u for u in admin_client.get(URL).json()['users']}
    assert by_name['student_u']['role'] is None


def test_no_password_or_email_is_ever_sent(admin_client, student):
    text = admin_client.get(URL).content.decode()
    assert 'pbkdf2' not in text and 'password' not in text.lower()
    assert student.email not in text and '@example.com' not in text


def test_timestamps_are_iso_8601_utc(admin_client, student):
    joined = admin_client.get(URL).json()['users'][0]['date_joined']
    assert joined.endswith('Z') and 'T' in joined


# ---- paging (SAD 4.3.1) ---------------------------------------------------------------------

@pytest.fixture
def forty_accounts(db):
    User.objects.bulk_create([User(username=f'bulk{i:02d}') for i in range(40)])


def test_default_page_has_20_and_reports_the_totals(admin_client, admin_user, forty_accounts):
    data = admin_client.get(URL).json()
    assert len(data['users']) == 20
    assert data['pagination'] == {'page': 1, 'page_size': 20, 'total': 41, 'pages': 3}


def test_second_page_continues_where_the_first_stopped(admin_client, admin_user, forty_accounts):
    first = admin_client.get(URL).json()['users']
    second = admin_client.get(URL + '?page=2').json()['users']
    assert not {u['id'] for u in first} & {u['id'] for u in second}
    assert first[-1]['username'] < second[0]['username']


def test_a_bad_page_is_400_in_the_standard_envelope(admin_client):
    response = admin_client.get(URL + '?page_size=1000')
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'VALIDATION_ERROR'


def test_the_list_does_not_query_once_per_user(admin_client, admin_user, forty_accounts,
                                               django_assert_max_num_queries):
    # session + user + count + one page of users with profiles: a handful, not ~40
    with django_assert_max_num_queries(8):
        assert admin_client.get(URL + '?page_size=40').status_code == 200
