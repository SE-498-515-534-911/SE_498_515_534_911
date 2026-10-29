"""US-37: the Admin panel screen (MLE-F-016, MLE-F-002; SAD 4.5.3)."""
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from audit.models import Action

pytestmark = pytest.mark.django_db
URL = '/accounts/admin-dashboard/'


def static_file(name):
    return Path(settings.BASE_DIR) / 'static' / 'wbmme' / name


# ---- access ------------------------------------------------------------------------------------

def test_the_admin_sees_the_panel(client, admin_user):
    client.force_login(admin_user)
    response = client.get(URL)
    assert response.status_code == 200
    html = response.content.decode()
    for element_id in ('admin-console', 'tab-users', 'tab-datasets', 'tab-audit',
                       'users-table', 'datasets-table', 'audit-table', 'audit-action'):
        assert f'id="{element_id}"' in html
    assert f'data-current-user-id="{admin_user.pk}"' in html


@pytest.mark.parametrize('fixture', ['student', 'scientist'])
def test_other_roles_are_refused(client, request, fixture):
    client.force_login(request.getfixturevalue(fixture))
    response = client.get(URL)
    assert response.status_code == 403
    assert b'admin-console' not in response.content


def test_a_visitor_is_sent_to_login(client, db):
    response = client.get(URL)
    assert response.status_code == 302 and response.url.startswith(reverse('accounts:login'))


# ---- the page itself holds no account data ---------------------------------------------------------

def test_the_page_does_not_contain_any_user_or_dataset_data(client, admin_user, student):
    client.force_login(admin_user)
    html = client.get(URL).content.decode()
    assert student.username not in html       # users are loaded by the script, over the API


def test_every_audit_event_is_offered_in_the_filter(client, admin_user):
    client.force_login(admin_user)
    html = client.get(URL).content.decode()
    for action in Action.values:
        assert f'<option value="{action}">' in html


# ---- assets ---------------------------------------------------------------------------------------------

def test_the_scripts_and_styles_are_served_from_this_project(client, admin_user):
    client.force_login(admin_user)
    html = client.get(URL).content.decode()
    assert 'wbmme/admin_console.js' in html and 'wbmme/admin_console.css' in html
    assert static_file('admin_console.js').is_file() and static_file('admin_console.css').is_file()
    assert 'cdn' not in html.lower()


def test_the_script_never_writes_user_supplied_text_as_html():
    """Usernames, dataset names and audit targets come from other people."""
    source = static_file('admin_console.js').read_text(encoding='utf-8')
    for unsafe in ('innerHTML', 'insertAdjacentHTML', 'document.write', 'outerHTML'):
        assert unsafe not in source


def test_the_script_asks_for_confirmation_before_every_destructive_action():
    source = static_file('admin_console.js').read_text(encoding='utf-8')
    assert source.count('window.confirm(') >= 3          # role change, (de)activation, dataset delete


def test_the_script_sends_the_csrf_token_and_only_calls_the_admin_api():
    source = static_file('admin_console.js').read_text(encoding='utf-8')
    assert 'X-CSRFToken' in source
    assert "'/api/admin/users" in source and "'/api/admin/datasets" in source and "'/api/admin/audit" in source


def test_the_admin_cannot_change_their_own_account_from_the_panel():
    """The controls are disabled for the signed-in Admin; the API refuses it as well."""
    source = static_file('admin_console.js').read_text(encoding='utf-8')
    assert 'select.disabled = isSelf' in source and 'button.disabled = isSelf' in source
