"""US-38: the audit log can be read but not edited in Django's admin site."""
import pytest
from django.contrib.auth import get_user_model

from audit import services
from audit.models import Action, AuditLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser_client(client):
    user = get_user_model().objects.create_superuser('boss', 'boss@example.com', 'Passw0rd1')
    client.force_login(user)
    services.record(Action.UPLOAD, user=user, target='dataset:1')
    return client


def test_an_admin_can_read_the_log(superuser_client):
    response = superuser_client.get('/admin/audit/auditlog/')
    assert response.status_code == 200
    assert b'dataset:1' in response.content


def test_nobody_can_add_an_entry(superuser_client):
    assert superuser_client.get('/admin/audit/auditlog/add/').status_code == 403


def test_nobody_can_change_an_entry(superuser_client):
    entry = AuditLog.objects.filter(action=Action.UPLOAD).first()
    response = superuser_client.post(f'/admin/audit/auditlog/{entry.pk}/change/', {'target': 'edited'})
    assert response.status_code in (302, 403)
    assert AuditLog.objects.get(pk=entry.pk).target == 'dataset:1'


def test_nobody_can_delete_an_entry(superuser_client):
    entry = AuditLog.objects.filter(action=Action.UPLOAD).first()
    assert superuser_client.get(f'/admin/audit/auditlog/{entry.pk}/delete/').status_code == 403
    assert superuser_client.post(f'/admin/audit/auditlog/{entry.pk}/delete/', {'post': 'yes'}).status_code == 403
    assert AuditLog.objects.filter(pk=entry.pk).exists()


def test_a_student_cannot_open_the_log_at_all(client, db):
    from accounts.models import Role
    student = get_user_model().objects.create_user('stu', 's@example.com', 'Passw0rd1')
    student.profile.role = Role.STUDENT
    student.profile.save()
    client.force_login(student)
    assert client.get('/admin/audit/auditlog/').status_code == 403
