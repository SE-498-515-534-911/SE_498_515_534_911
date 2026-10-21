"""Login lockout: 5 failures in 10 minutes block the account for 15 (MLE-SR-007c)."""
import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts import throttle

User = get_user_model()
LOGIN = '/api/auth/login'


@pytest.fixture
def account(db):
    return User.objects.create_user('lock_me', 'l@example.com', 'Passw0rd1')


@pytest.fixture
def clock(monkeypatch):
    """A clock the test can move forward."""
    state = {'now': timezone.now()}
    monkeypatch.setattr(timezone, 'now', lambda: state['now'])

    def advance(**kwargs):
        state['now'] += timedelta(**kwargs)

    return advance


def api_login(client, password, username='lock_me'):
    return client.post(LOGIN, json.dumps({'username': username, 'password': password}),
                       content_type='application/json')


def fail(client, times):
    for _ in range(times):
        assert api_login(client, 'Wrong#123').status_code == 401


def test_fifth_failure_locks_the_account(client, account, clock):
    fail(client, 4)
    assert not throttle.is_locked('lock_me')
    fail(client, 1)
    assert throttle.is_locked('lock_me')


def test_locked_account_gets_429_even_with_the_right_password(client, account, clock):
    fail(client, 5)
    response = api_login(client, 'Passw0rd1')
    assert response.status_code == 429
    assert response.json()['error']['code'] == 'ACCOUNT_LOCKED'
    assert '_auth_user_id' not in client.session


def test_lock_lasts_15_minutes(client, account, clock):
    fail(client, 5)
    clock(minutes=14)
    assert api_login(client, 'Passw0rd1').status_code == 429
    clock(minutes=2)  # 16 minutes after the lock began
    assert api_login(client, 'Passw0rd1').status_code == 200


def test_failures_older_than_10_minutes_do_not_add_up(client, account, clock):
    fail(client, 4)
    clock(minutes=11)
    fail(client, 4)  # a new window: 4 failures, still below 5
    assert not throttle.is_locked('lock_me')


def test_success_resets_the_count(client, account, clock):
    fail(client, 4)
    assert api_login(client, 'Passw0rd1').status_code == 200
    client.post('/api/auth/logout')
    fail(client, 4)
    assert not throttle.is_locked('lock_me')


def test_username_is_case_insensitive(client, account, clock):
    for _ in range(5):
        api_login(client, 'bad', username='LOCK_ME')
    assert throttle.is_locked('lock_me')


def test_unknown_usernames_are_throttled_too(client, db, clock):
    for _ in range(5):
        api_login(client, 'bad', username='ghost')
    assert throttle.is_locked('ghost')


def test_html_login_uses_the_same_lockout(client, account, clock):
    for _ in range(5):
        client.post('/accounts/login/', {'username': 'lock_me', 'password': 'Wrong#123'})
    response = client.post('/accounts/login/', {'username': 'lock_me', 'password': 'Passw0rd1'})
    assert response.status_code == 200
    assert b'Too many failed logins' in response.content
    assert '_auth_user_id' not in client.session


def test_html_login_deactivated_account_refused(client, account):
    """MLE-F-001: a deactivated account cannot log in through the web form either."""
    account.is_active = False
    account.save()
    response = client.post('/accounts/login/', {'username': 'lock_me', 'password': 'Passw0rd1'})
    assert response.status_code == 200
    assert b'Incorrect username or password' in response.content
    assert '_auth_user_id' not in client.session
