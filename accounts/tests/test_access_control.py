import pytest
from django.urls import reverse

ADMIN_URL = 'accounts:admin_dashboard'


def get_status(client, user, url_name):
    if user is not None:
        client.force_login(user)
    return client.get(reverse(url_name)).status_code


# Expected access per page (SRS Table 4.1-1). None means "not logged in".
# Every URL of the accounts app must appear here, so a new page cannot be
# added without deciding who may open it (deny by default, MLE-F-002).
PAGE_RULES = {
    'accounts:home': {'STUDENT': 200, 'DATA_SCIENTIST': 200, 'ADMIN': 200, None: 302},
    ADMIN_URL: {'STUDENT': 403, 'DATA_SCIENTIST': 403, 'ADMIN': 200, None: 302},
}
PUBLIC_PAGES = {'accounts:register', 'accounts:login', 'accounts:logout'}


def user_for(role, student, scientist, admin_user):
    return {'STUDENT': student, 'DATA_SCIENTIST': scientist,
            'ADMIN': admin_user, None: None}[role]


@pytest.mark.parametrize('url_name', sorted(PAGE_RULES))
@pytest.mark.parametrize('role', ['STUDENT', 'DATA_SCIENTIST', 'ADMIN', None])
def test_page_access_matrix(client, db, student, scientist, admin_user, url_name, role):
    user = user_for(role, student, scientist, admin_user)
    assert get_status(client, user, url_name) == PAGE_RULES[url_name][role]


def test_every_accounts_url_has_an_access_rule():
    from accounts.urls import urlpatterns
    names = {f'accounts:{p.name}' for p in urlpatterns}
    assert names == set(PAGE_RULES) | PUBLIC_PAGES


def test_anonymous_redirected_to_login_with_next(client, db):
    response = client.get(reverse(ADMIN_URL))
    assert response.status_code == 302
    assert response.url.startswith(reverse('accounts:login'))


def test_user_without_profile_is_denied_by_default(client, student):
    from accounts.models import Profile
    Profile.objects.filter(user=student).delete()
    client.force_login(student)
    assert client.get(reverse(ADMIN_URL)).status_code == 403


def test_admin_link_shown_to_admin_only(client, student, admin_user):
    client.force_login(student)
    assert b'Admin dashboard' not in client.get(reverse('accounts:home')).content
    client.force_login(admin_user)
    assert b'Admin dashboard' in client.get(reverse('accounts:home')).content


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
