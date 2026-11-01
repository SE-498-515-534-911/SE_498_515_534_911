"""US-37: PATCH /api/admin/users/<id> (MLE-F-016, MLE-F-002, MLE-SR-005; SAD 4.3.2)."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from audit.models import Action, AuditLog

pytestmark = pytest.mark.django_db

User = get_user_model()
PASSWORD = 'Passw0rd1'


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


def patch(client, user, payload):
    body = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
    return client.patch(f'/api/admin/users/{user.pk}', body, content_type='application/json')


def fresh(user):
    return User.objects.select_related('profile').get(pk=user.pk)


def updates():
    return list(AuditLog.objects.filter(action=Action.ADMIN_USER_UPDATE))


# ---- change a role -----------------------------------------------------------------------

def test_the_admin_changes_a_role(admin_client, student):
    response = patch(admin_client, student, {'role': 'DATA_SCIENTIST'})
    assert response.status_code == 200
    assert response.json()['user']['role'] == 'DATA_SCIENTIST'
    assert fresh(student).role == 'DATA_SCIENTIST'


def test_the_new_role_works_on_the_accounts_very_next_request(admin_client, student):
    other = Client()
    other.force_login(student)
    assert other.get('/accounts/admin-dashboard/').status_code == 403
    patch(admin_client, student, {'role': 'ADMIN'})
    assert other.get('/accounts/admin-dashboard/').status_code == 200   # promoted
    patch(admin_client, student, {'role': 'STUDENT'})
    assert other.get('/accounts/admin-dashboard/').status_code == 403   # demoted again


def test_an_account_without_a_profile_gets_one(admin_client, student):
    student.profile.delete()
    patch(admin_client, student, {'role': 'STUDENT'})
    assert fresh(student).role == 'STUDENT'


# ---- deactivate and reactivate -----------------------------------------------------------

def test_deactivating_stops_the_account_logging_in(admin_client, student):
    assert patch(admin_client, student, {'is_active': False}).json()['user']['is_active'] is False
    response = Client().post('/api/auth/login', json.dumps({'username': 'student_u', 'password': PASSWORD}),
                             content_type='application/json')
    assert response.status_code == 401            # the same generic refusal as a wrong password


def test_deactivating_ends_a_session_that_is_already_open(admin_client, student):
    open_session = Client()
    open_session.force_login(student)
    assert open_session.get('/accounts/').status_code == 200
    patch(admin_client, student, {'is_active': False})
    response = open_session.get('/accounts/')
    assert response.status_code == 302 and '/login/' in response.url


def test_reactivating_lets_the_account_log_in_again(admin_client, student):
    patch(admin_client, student, {'is_active': False})
    patch(admin_client, student, {'is_active': True})
    response = Client().post('/api/auth/login', json.dumps({'username': 'student_u', 'password': PASSWORD}),
                             content_type='application/json')
    assert response.status_code == 200


def test_a_role_and_a_status_can_change_together_in_one_entry(admin_client, student):
    patch(admin_client, student, {'role': 'DATA_SCIENTIST', 'is_active': False})
    account = fresh(student)
    assert account.role == 'DATA_SCIENTIST' and account.is_active is False
    assert len(updates()) == 1


# ---- the audit log (MLE-SR-005) ------------------------------------------------------------

def test_a_change_is_logged_with_who_what_and_when(admin_client, admin_user, student):
    patch(admin_client, student, {'role': 'DATA_SCIENTIST'})
    entry = updates()[0]
    assert entry.user == admin_user
    assert entry.target == f'user:{student.pk} role->DATA_SCIENTIST'
    assert entry.ip_address == '127.0.0.1' and entry.timestamp


@pytest.mark.parametrize('payload,expected', [
    ({'is_active': False}, 'deactivated'),
    ({'is_active': True}, None),            # already active: nothing changes
])
def test_deactivation_is_logged_and_a_no_op_is_not(admin_client, student, payload, expected):
    patch(admin_client, student, payload)
    if expected:
        assert expected in updates()[0].target
    else:
        assert updates() == []


def test_setting_the_same_role_changes_nothing_and_logs_nothing(admin_client, student):
    response = patch(admin_client, student, {'role': 'STUDENT'})
    assert response.status_code == 200 and updates() == []


def test_the_log_holds_no_password(admin_client, student):
    patch(admin_client, student, {'role': 'DATA_SCIENTIST'})
    stored = json.dumps(list(AuditLog.objects.values()), default=str)
    assert PASSWORD not in stored and 'pbkdf2' not in stored


# ---- bad requests change nothing --------------------------------------------------------------

@pytest.mark.parametrize('role', ['SUPERUSER', 'admin', 'Student', '', None, 5, ['ADMIN']])
def test_an_invalid_role_is_refused(admin_client, student, role):
    response = patch(admin_client, student, {'role': role})
    assert response.status_code == 400
    assert response.json()['error']['details']['field'] == 'role'
    assert fresh(student).role == 'STUDENT' and updates() == []


@pytest.mark.parametrize('value', ['false', 0, 1, None, 'yes'])
def test_is_active_must_be_a_real_boolean(admin_client, student, value):
    assert patch(admin_client, student, {'is_active': value}).status_code == 400
    assert fresh(student).is_active is True


@pytest.mark.parametrize('field', ['is_superuser', 'is_staff', 'password', 'username', 'email', 'id'])
def test_fields_other_than_role_and_status_cannot_be_changed(admin_client, student, field):
    """Mass-assignment guard: a crafted request cannot touch anything else."""
    before = fresh(student)
    response = patch(admin_client, student, {field: 'x', 'role': 'DATA_SCIENTIST'})
    assert response.status_code == 400
    after = fresh(student)
    assert (after.username, after.email, after.is_staff, after.is_superuser, after.password, after.role) == \
           (before.username, before.email, before.is_staff, before.is_superuser, before.password, 'STUDENT')


@pytest.mark.parametrize('body', ['{}', '[]', 'not json', ''])
def test_an_empty_or_malformed_body_is_refused(admin_client, student, body):
    assert patch(admin_client, student, body).status_code == 400


def test_an_unknown_account_is_404(admin_client, admin_user):
    response = admin_client.patch('/api/admin/users/999999', json.dumps({'role': 'STUDENT'}),
                                  content_type='application/json')
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'NOT_FOUND'


# ---- an Admin cannot lock themselves out --------------------------------------------------------

@pytest.mark.parametrize('payload', [{'role': 'STUDENT'}, {'is_active': False}, {'role': 'ADMIN'}])
def test_an_admin_cannot_change_their_own_account(admin_client, admin_user, payload):
    response = patch(admin_client, admin_user, payload)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'UNPROCESSABLE'
    assert fresh(admin_user).role == 'ADMIN' and fresh(admin_user).is_active
    assert updates() == []


def test_an_admin_can_demote_another_admin(admin_client, admin_user):
    other = User.objects.create_user('second_admin', 's@example.com', PASSWORD)
    other.profile.role = 'ADMIN'
    other.profile.save()
    assert patch(admin_client, other, {'role': 'STUDENT'}).status_code == 200
    assert fresh(admin_user).role == 'ADMIN'      # at least one Admin always remains


# ---- who may call ---------------------------------------------------------------------------------

@pytest.mark.parametrize('fixture', ['student', 'scientist'])
def test_other_roles_cannot_change_anything_even_their_own_role(client, request, fixture):
    user = request.getfixturevalue(fixture)
    client.force_login(user)
    response = patch(client, user, {'role': 'ADMIN'})            # trying to promote themselves
    assert response.status_code == 403
    assert fresh(user).role != 'ADMIN'


def test_a_visitor_gets_401(client, student):
    assert patch(client, student, {'role': 'ADMIN'}).status_code == 401
    assert fresh(student).role == 'STUDENT'


def test_other_methods_are_not_allowed(admin_client, student):
    assert admin_client.get(f'/api/admin/users/{student.pk}').status_code == 405
    assert admin_client.post(f'/api/admin/users/{student.pk}').status_code == 405
    assert admin_client.delete(f'/api/admin/users/{student.pk}').status_code == 405


def test_the_csrf_token_is_required(admin_user, student):
    """MLE-SR-007(d): a state-changing request without the token is refused."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    response = patch(client, student, {'role': 'ADMIN'})
    assert response.status_code == 403
    assert fresh(student).role == 'STUDENT'
