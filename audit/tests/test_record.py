"""US-38: writing audit entries (MLE-SR-005(b); SAD 4.4.4)."""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from audit import services
from audit.models import Action, AuditLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user('audited', 'a@example.com', 'Passw0rd1')


def request_from(ip):
    request = RequestFactory().get('/x/')
    request.META['REMOTE_ADDR'] = ip
    return request


def test_an_entry_stores_user_action_target_ip_and_time(user):
    services.record(Action.UPLOAD, user=user, target='dataset:7', request=request_from('203.0.113.9'))
    entry = AuditLog.objects.get()
    assert entry.user == user
    assert entry.action == 'UPLOAD'
    assert entry.target == 'dataset:7'
    assert entry.ip_address == '203.0.113.9'
    assert entry.timestamp is not None


def test_an_anonymous_visitor_is_stored_without_a_user():
    services.record(Action.LOGIN_FAILED, user=AnonymousUser(), request=request_from('203.0.113.9'))
    assert AuditLog.objects.get().user is None


def test_an_ipv6_address_is_kept():
    services.record(Action.LOGOUT, request=request_from('2001:db8::1'))
    assert AuditLog.objects.get().ip_address == '2001:db8::1'


@pytest.mark.parametrize('bad', ['', 'unknown', 'not an ip', '999.1.1.1'])
def test_an_invalid_address_is_stored_as_unknown(bad):
    services.record(Action.LOGOUT, request=request_from(bad))
    assert AuditLog.objects.get().ip_address is None


def test_the_forwarded_for_header_is_ignored():
    """A client could fake X-Forwarded-For, so only REMOTE_ADDR is trusted."""
    request = request_from('203.0.113.9')
    request.META['HTTP_X_FORWARDED_FOR'] = '6.6.6.6'
    services.record(Action.LOGOUT, request=request)
    assert AuditLog.objects.get().ip_address == '203.0.113.9'


def test_without_a_request_the_current_request_address_is_used():
    token = services.current_ip.set('198.51.100.4')
    try:
        services.record(Action.TRAIN_DONE, target='run:1')
    finally:
        services.current_ip.reset(token)
    assert AuditLog.objects.get().ip_address == '198.51.100.4'


def test_a_long_target_is_cut_to_fit():
    services.record(Action.ACCESS_DENIED, target='x' * 500)
    assert len(AuditLog.objects.get().target) == 100


def test_a_failure_to_write_never_breaks_the_caller(monkeypatch, caplog):
    def boom(**kwargs):
        raise RuntimeError('database is on fire')
    monkeypatch.setattr(AuditLog.objects, 'create', boom)
    services.record(Action.LOGOUT)              # must not raise
    assert 'could not be written' in caplog.text


def test_entries_cannot_be_changed_once_written():
    services.record(Action.LOGOUT)
    entry = AuditLog.objects.get()
    entry.action = Action.UPLOAD
    with pytest.raises(ValueError, match='cannot be changed'):
        entry.save()
    assert AuditLog.objects.get().action == 'LOGOUT'


def test_entries_outlive_a_deleted_account(user):
    services.record(Action.UPLOAD, user=user, target='dataset:1')
    user.delete()
    entry = AuditLog.objects.get()
    assert entry.user is None and entry.target == 'dataset:1'


# ---- failed logins -----------------------------------------------------------------

def test_a_failed_login_is_linked_to_an_existing_account_ignoring_case(user):
    services.record_login_failed('AUDITED', request=request_from('203.0.113.9'))
    entry = AuditLog.objects.get()
    assert entry.action == 'LOGIN_FAILED' and entry.user == user


def test_a_failed_login_for_an_unknown_name_has_no_user_and_never_stores_the_name():
    services.record_login_failed('Passw0rd1-typed-in-the-wrong-box', request=request_from('203.0.113.9'))
    entry = AuditLog.objects.get()
    assert entry.user is None
    assert 'Passw0rd1' not in f'{entry.target} {entry.action} {entry.user_id}'


@pytest.mark.parametrize('name', [None, '', 123])
def test_a_failed_login_with_an_odd_name_is_still_logged(name):
    services.record_login_failed(name)
    assert AuditLog.objects.get().user is None
