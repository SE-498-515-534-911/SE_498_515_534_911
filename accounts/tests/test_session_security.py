"""Sessions, cookies and CSRF (MLE-SR-007 a, b, d)."""
import json
from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client
from django.utils import timezone

User = get_user_model()
LOGIN = '/api/auth/login'
CREDENTIALS = json.dumps({'username': 'sess_user', 'password': 'Passw0rd1'})


@pytest.fixture
def account(db):
    return User.objects.create_user('sess_user', 's@example.com', 'Passw0rd1')


def login(client):
    return client.post(LOGIN, CREDENTIALS, content_type='application/json')


# --- 30 minute inactivity (MLE-SR-007a) -------------------------------------

def test_session_settings_are_30_minutes_of_inactivity():
    assert settings.SESSION_COOKIE_AGE == 30 * 60
    assert settings.SESSION_SAVE_EVERY_REQUEST is True  # idle time, not total time


def test_each_request_renews_the_30_minute_expiry(client, account):
    login(client)
    client.get('/accounts/')
    assert client.session.get_expiry_age() == pytest.approx(1800, abs=5)


def test_idle_session_is_ended(client, account):
    login(client)
    assert client.get('/accounts/').status_code == 200
    # Pretend the last request was 31 minutes ago.
    Session.objects.update(expire_date=timezone.now() - timedelta(minutes=1))
    response = client.get('/accounts/')
    assert response.status_code == 302 and '/login/' in response.url


# --- cookie flags (MLE-SR-007b) ---------------------------------------------

def test_session_cookie_is_httponly(client, account):
    cookie = login(client).cookies['sessionid']
    assert cookie['httponly']
    assert cookie['samesite'] == 'Lax'


def test_session_cookie_is_secure_on_https_builds(client, account, settings):
    settings.SESSION_COOKIE_SECURE = True  # what WBMME_HTTPS=1 switches on
    assert login(client).cookies['sessionid']['secure']


def test_session_cookie_not_secure_by_default_for_local_http(client, account):
    assert not login(client).cookies['sessionid']['secure']


def test_wbmme_https_env_switches_secure_cookies_on(monkeypatch):
    import importlib
    import config.settings as project_settings
    monkeypatch.setenv('WBMME_HTTPS', '1')
    try:
        assert importlib.reload(project_settings).SESSION_COOKIE_SECURE is True
    finally:
        monkeypatch.delenv('WBMME_HTTPS')
        importlib.reload(project_settings)


# --- CSRF (MLE-SR-007d) -------------------------------------------------------

@pytest.mark.parametrize('url', ['/api/auth/login', '/api/auth/register', '/api/auth/logout'])
def test_api_post_without_csrf_token_is_403_envelope(db, url):
    client = Client(enforce_csrf_checks=True)
    response = client.post(url, CREDENTIALS, content_type='application/json')
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'FORBIDDEN'


def test_html_post_without_csrf_token_is_403(db):
    client = Client(enforce_csrf_checks=True)
    assert client.post('/accounts/login/', {'username': 'x', 'password': 'y'}).status_code == 403


def test_api_post_with_csrf_header_is_accepted(account):
    client = Client(enforce_csrf_checks=True)
    client.get('/accounts/login/')  # the page sets the csrftoken cookie
    token = client.cookies['csrftoken'].value
    response = client.post(LOGIN, CREDENTIALS, content_type='application/json',
                           HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200
