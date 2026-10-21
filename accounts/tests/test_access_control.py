import pytest
from django.urls import reverse

ADMIN_URL = 'accounts:admin_dashboard'
WORKSPACE_URL = 'accounts:workspace'


def get_status(client, user, url_name):
    if user is not None:
        client.force_login(user)
    return client.get(reverse(url_name)).status_code


def test_student_cannot_open_admin_dashboard(client, student):
    assert get_status(client, student, ADMIN_URL) == 403


def test_data_scientist_cannot_open_admin_dashboard(client, scientist):
    assert get_status(client, scientist, ADMIN_URL) == 403


def test_admin_can_open_admin_dashboard(client, admin_user):
    assert get_status(client, admin_user, ADMIN_URL) == 200


def test_student_cannot_open_workspace(client, student):
    assert get_status(client, student, WORKSPACE_URL) == 403


@pytest.mark.parametrize('fixture', ['scientist', 'admin_user'])
def test_workspace_allowed_roles(client, request, fixture):
    assert get_status(client, request.getfixturevalue(fixture), WORKSPACE_URL) == 200


@pytest.mark.parametrize('url_name', [ADMIN_URL, WORKSPACE_URL])
def test_anonymous_redirected_to_login(client, db, url_name):
    response = client.get(reverse(url_name))
    assert response.status_code == 302
    assert response.url.startswith(reverse('accounts:login'))


def test_student_blocked_from_django_admin_site(client, student):
    client.force_login(student)
    assert client.get('/admin/').status_code == 403
    assert client.get('/admin/auth/user/').status_code == 403


def test_non_staff_scientist_blocked_from_django_admin_site(client, scientist):
    client.force_login(scientist)
    assert client.get('/admin/').status_code == 403


def test_admin_role_reaches_django_admin_when_staff(client, admin_user):
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()
    client.force_login(admin_user)
    assert client.get('/admin/').status_code == 200


def test_denied_page_uses_403_template(client, student):
    client.force_login(student)
    response = client.get(reverse(ADMIN_URL))
    assert b'Access denied' in response.content
