"""US-38: logins, logouts, failed logins and registrations are logged (MLE-SR-005(b); SAD 4.4.4)."""
import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from audit.models import Action, AuditLog

pytestmark = pytest.mark.django_db

User = get_user_model()
PASSWORD = 'Passw0rd1'
WRONG = 'Wr0ng-secret-99'


@pytest.fixture
def account():
    return User.objects.create_user('audit_me', 'audit@example.com', PASSWORD)


def entries(action):
    return list(AuditLog.objects.filter(action=action))


def api(client, url, payload):
    return client.post(url, json.dumps(payload), content_type='application/json')


def everything_stored():
    """Every value of every entry as one text, to prove a secret is nowhere in it."""
    rows = AuditLog.objects.values('user_id', 'action', 'target', 'ip_address', 'timestamp')
    return json.dumps(list(rows), default=str)


# ---- login ------------------------------------------------------------------------

def test_web_login_is_logged_with_user_time_and_address(client, account):
    before = timezone.now()
    client.post('/accounts/login/', {'username': 'audit_me', 'password': PASSWORD})
    entry = entries(Action.LOGIN_SUCCESS)[0]
    assert entry.user == account
    assert entry.ip_address == '127.0.0.1'
    assert before - timedelta(seconds=5) <= entry.timestamp <= timezone.now()


def test_api_login_is_logged(client, account):
    api(client, '/api/auth/login', {'username': 'audit_me', 'password': PASSWORD})
    assert [e.user for e in entries(Action.LOGIN_SUCCESS)] == [account]


# ---- failed login -----------------------------------------------------------------

@pytest.mark.parametrize('how', ['web', 'api'])
def test_failed_login_is_logged_against_the_account(client, account, how):
    if how == 'web':
        client.post('/accounts/login/', {'username': 'audit_me', 'password': WRONG})
    else:
        api(client, '/api/auth/login', {'username': 'audit_me', 'password': WRONG})
    failed = entries(Action.LOGIN_FAILED)
    assert [e.user for e in failed] == [account]
    assert not entries(Action.LOGIN_SUCCESS)


@pytest.mark.parametrize('how', ['web', 'api'])
def test_no_password_is_ever_written_to_the_log(client, account, how):
    """MLE-SR-005(b): the log contains no credentials."""
    for password in (WRONG, PASSWORD):
        if how == 'web':
            client.post('/accounts/login/', {'username': 'audit_me', 'password': password})
        else:
            api(client, '/api/auth/login', {'username': 'audit_me', 'password': password})
    text = everything_stored()
    assert WRONG not in text and PASSWORD not in text


def test_failed_login_for_an_unknown_name_has_no_user_and_does_not_store_the_name(client, db):
    api(client, '/api/auth/login', {'username': 'ghost_account', 'password': WRONG})
    entry = entries(Action.LOGIN_FAILED)[0]
    assert entry.user is None
    assert 'ghost_account' not in everything_stored()


def test_a_deactivated_account_login_is_logged_as_failed(client, account):
    account.is_active = False
    account.save()
    api(client, '/api/auth/login', {'username': 'audit_me', 'password': PASSWORD})
    assert [e.user for e in entries(Action.LOGIN_FAILED)] == [account]


@pytest.mark.parametrize('how', ['web', 'api'])
def test_attempts_while_locked_out_are_logged_too(client, account, how):
    for _ in range(5):
        api(client, '/api/auth/login', {'username': 'audit_me', 'password': WRONG})
    assert len(entries(Action.LOGIN_FAILED)) == 5

    if how == 'web':
        client.post('/accounts/login/', {'username': 'audit_me', 'password': PASSWORD})
    else:
        api(client, '/api/auth/login', {'username': 'audit_me', 'password': PASSWORD})
    failed = entries(Action.LOGIN_FAILED)
    assert len(failed) == 6
    assert sorted(e.target for e in failed).count('locked') == 1
    assert not entries(Action.LOGIN_SUCCESS)


# ---- logout -----------------------------------------------------------------------

def test_web_logout_is_logged(client, account):
    client.force_login(account)
    AuditLog.objects.all().delete()
    client.post('/accounts/logout/')
    assert [e.user for e in entries(Action.LOGOUT)] == [account]


def test_api_logout_is_logged(client, account):
    client.force_login(account)
    AuditLog.objects.all().delete()
    client.post('/api/auth/logout')
    assert [e.user for e in entries(Action.LOGOUT)] == [account]


# ---- registration -----------------------------------------------------------------

def test_web_registration_is_logged_against_the_new_account(client, db):
    client.post('/accounts/register/', {
        'username': 'newbie', 'email': 'n@example.com', 'password': PASSWORD,
        'confirm_password': PASSWORD, 'role': 'STUDENT'})
    user = User.objects.get(username='newbie')
    entry = entries(Action.REGISTER)[0]
    assert entry.user == user and entry.target == f'user:{user.pk}'


def test_api_registration_is_logged(client, db):
    api(client, '/api/auth/register', {
        'username': 'newbie', 'email': 'n@example.com', 'password': PASSWORD, 'role': 'DATA_SCIENTIST'})
    user = User.objects.get(username='newbie')
    assert [(e.user, e.target) for e in entries(Action.REGISTER)] == [(user, f'user:{user.pk}')]
    assert PASSWORD not in everything_stored()


def test_a_refused_registration_is_not_logged(client, db):
    api(client, '/api/auth/register', {
        'username': 'x', 'email': 'bad', 'password': 'short', 'role': 'ADMIN'})
    assert not entries(Action.REGISTER)
