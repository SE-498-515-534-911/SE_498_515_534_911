"""US-22: the Results screen (MLE-F-011; SAD 4.5.3)."""
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from .conftest import train_run

pytestmark = pytest.mark.django_db


def page(client, run_id):
    return client.get(reverse('run-results', args=[run_id]))


def test_anonymous_user_is_sent_to_login(client, trained_run):
    response = page(client, trained_run.pk)
    assert response.status_code == 302
    assert response.url.startswith(reverse('accounts:login'))


def test_admin_is_forbidden(client, admin_user, trained_run):
    client.force_login(admin_user)
    assert page(client, trained_run.pk).status_code == 403


def test_another_users_run_is_404(client, other_user, trained_run):
    client.force_login(other_user)
    assert page(client, trained_run.pk).status_code == 404


def test_missing_run_is_404(client, student):
    client.force_login(student)
    assert page(client, 9999).status_code == 404


@pytest.mark.parametrize('fixture', ['student', 'scientist'])
def test_owner_sees_the_page_wired_to_the_evaluate_api(client, request, fixture):
    user = request.getfixturevalue(fixture)
    run = train_run(user)
    client.force_login(user)
    response = page(client, run.pk)
    assert response.status_code == 200
    html = response.content.decode()
    assert f'data-api-url="/api/evaluate/{run.pk}"' in html
    assert 'id="metric-chart"' in html and 'id="confusion-matrix"' in html
    assert 'wbmme/vendor/chart.umd.min.js' in html and 'wbmme/results.js' in html


def test_chart_library_and_scripts_are_served_locally():
    """The page must work offline: Chart.js is vendored, not loaded from a CDN."""
    static = Path(settings.BASE_DIR) / 'static' / 'wbmme'
    assert (static / 'vendor' / 'chart.umd.min.js').stat().st_size > 100_000
    assert (static / 'results.js').is_file() and (static / 'results.css').is_file()


def test_script_never_writes_user_supplied_class_names_as_html():
    """Class names come from the user's CSV, so they must only be set as text."""
    source = (Path(settings.BASE_DIR) / 'static' / 'wbmme' / 'results.js').read_text(encoding='utf-8')
    assert 'innerHTML' not in source
    assert 'insertAdjacentHTML' not in source
    assert 'document.write' not in source


def test_page_has_a_feature_importance_section_for_the_script_to_fill(client, student, trained_run):
    client.force_login(student)
    html = page(client, trained_run.pk).content.decode()
    for element_id in ('importance-chart', 'importance-table', 'importance-message', 'importance-content'):
        assert f'id="{element_id}"' in html


def test_script_shows_the_not_available_message_from_the_api():
    """Models without importance (k-NN) must show the API's message, not an empty panel."""
    source = (Path(settings.BASE_DIR) / 'static' / 'wbmme' / 'results.js').read_text(encoding='utf-8')
    assert 'feature_importance_message' in source
    assert 'innerHTML' not in source
