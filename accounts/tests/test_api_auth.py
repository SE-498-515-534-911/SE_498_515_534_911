"""JSON auth API (SAD 4.3.7): US-15, MLE-F-001, MLE-SR-001."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()

REGISTER = '/api/auth/register'
LOGIN = '/api/auth/login'
LOGOUT = '/api/auth/logout'

VALID = {'username': 'api_user', 'email': 'api@example.com',
         'password': 'Passw0rd1', 'role': 'DATA_SCIENTIST'}


def post(client, url, payload):
    return client.post(url, json.dumps(payload), content_type='application/json')


def assert_envelope(response, code, status):
    """Every error uses the SAD 4.3.1 envelope."""
    assert response.status_code == status
    error = response.json()['error']
    assert error['code'] == code
    assert set(error) == {'code', 'message', 'details', 'request_id'}
    assert error['request_id']
    return error


@pytest.fixture
def account(db):
    return User.objects.create_user('api_user', 'api@example.com', 'Passw0rd1')


# --- register -------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize('role', ['STUDENT', 'DATA_SCIENTIST'])
def test_register_creates_account_with_role(client, role):
    response = post(client, REGISTER, {**VALID, 'role': role})
    assert response.status_code == 201
    body = response.json()['user']
    assert body['username'] == 'api_user' and body['role'] == role
    user = User.objects.get(username='api_user')
    assert user.role == role
    assert user.password.startswith('pbkdf2_sha256$')  # hashed (MLE-SR-001)
    assert 'password' not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('role', ['ADMIN', 'admin', 'ROOT', None])
def test_register_rejects_admin_and_unknown_roles(client, role):
    response = post(client, REGISTER, {**VALID, 'role': role})
    error = assert_envelope(response, 'VALIDATION_ERROR', 400)
    assert 'role' in error['details']['fields']
    assert not User.objects.exists()


@pytest.mark.django_db
def test_register_reports_one_message_per_faulty_field(client):
    response = post(client, REGISTER, {'username': 'ab', 'email': 'nope',
                                       'password': 'short1', 'role': 'STUDENT'})
    error = assert_envelope(response, 'VALIDATION_ERROR', 400)
    assert set(error['details']['fields']) == {'username', 'email', 'password'}
    assert error['details']['field'] in error['details']['fields']
    assert not User.objects.exists()


@pytest.mark.django_db
def test_register_rejects_duplicate_username(client, account):
    response = post(client, REGISTER, {**VALID, 'email': 'other@example.com'})
    error = assert_envelope(response, 'VALIDATION_ERROR', 400)
    assert 'username' in error['details']['fields']


@pytest.mark.django_db
@pytest.mark.parametrize('body', ['not json', '[1, 2]', ''])
def test_register_rejects_bad_json(client, body):
    response = client.post(REGISTER, body, content_type='application/json')
    assert_envelope(response, 'VALIDATION_ERROR', 400)


# --- login ----------------------------------------------------------------

def test_login_returns_user_and_starts_session(client, account):
    response = post(client, LOGIN, {'username': 'api_user', 'password': 'Passw0rd1'})
    assert response.status_code == 200
    user = response.json()['user']
    assert user == {'id': account.pk, 'username': 'api_user', 'role': 'STUDENT'}
    assert client.get('/accounts/').status_code == 200  # session works


def test_wrong_password_is_401_invalid_credentials_with_no_session(client, account):
    response = post(client, LOGIN, {'username': 'api_user', 'password': 'Wrong#123'})
    error = assert_envelope(response, 'INVALID_CREDENTIALS', 401)
    assert error['message'] == 'Invalid username or password.'
    assert '_auth_user_id' not in client.session


def test_unknown_user_gets_the_same_answer_as_wrong_password(client, account):
    wrong = post(client, LOGIN, {'username': 'api_user', 'password': 'Wrong#123'})
    unknown = post(Client(), LOGIN, {'username': 'ghost', 'password': 'Passw0rd1'})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()['error']['message'] == wrong.json()['error']['message']


def test_deactivated_account_cannot_log_in(client, account):
    """MLE-F-001 / TC-AUTH-01 step 7: same generic refusal, no session."""
    account.is_active = False
    account.save()
    response = post(client, LOGIN, {'username': 'api_user', 'password': 'Passw0rd1'})
    assert_envelope(response, 'INVALID_CREDENTIALS', 401)
    assert '_auth_user_id' not in client.session


@pytest.mark.parametrize('payload', [{}, {'username': 'x'}, {'username': 1, 'password': 2}])
def test_login_requires_username_and_password(client, account, payload):
    assert_envelope(post(client, LOGIN, payload), 'VALIDATION_ERROR', 400)


# --- logout ---------------------------------------------------------------

def test_logout_ends_session(client, account):
    client.force_login(account)
    assert client.post(LOGOUT).status_code == 204
    assert client.get('/accounts/').status_code == 302


def test_logout_requires_login(client, db):
    assert_envelope(client.post(LOGOUT), 'AUTH_REQUIRED', 401)


@pytest.mark.parametrize('url', [REGISTER, LOGIN, LOGOUT])
def test_get_is_not_allowed(client, db, url):
    assert_envelope(client.get(url), 'METHOD_NOT_ALLOWED', 405)
