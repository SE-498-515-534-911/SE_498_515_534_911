"""Regression tests for four problems found by using the web pages by hand.

* Datasets page: the Preview button did nothing (MLE-F-004).
* Models page: a maximum depth of 5 was refused as "not a whole number" (MLE-F-008).
* Training page: it never noticed that training was finished and had no way to the results (MLE-F-009).
* Dashboard: the "Configure a model" and "Review evaluation" tiles still said "Planned".

Most of the behaviour lives in each page's JavaScript, which pytest cannot run. The fixes were
checked in a real browser; these tests pin the parts the server renders and the key lines of the
scripts, so that the same mistakes cannot come back unnoticed.
"""
import json
import re

import pytest
from django.contrib.auth import get_user_model

from datasets.models import Dataset

pytestmark = pytest.mark.django_db

# Awkward but legal values: quotes, apostrophes, backslashes, unicode, and text that looks like HTML.
AWKWARD_PROFILE = {
    'preview': [["it's", 'say "hi"', 'back\\slash', 'naïve ✓', '</script><b>x</b>', '&amp;']],
    'columns': [
        {'name': "col'umn", 'type': 'text', 'missing_values': 0},
        {'name': 'with "quotes"', 'type': 'text', 'missing_values': 1},
    ],
}


@pytest.fixture
def student_client(client):
    user = get_user_model().objects.create_user('ui_student', 'ui@example.com', 'Passw0rd1')
    client.force_login(user)
    return client, user


def make_dataset(user, name, profile):
    return Dataset.objects.create(owner=user, name=name, file_path='unused', size_bytes=10,
                                  rows=1, columns=2, profile_json=profile)


# ---- Datasets page: Preview -------------------------------------------------------------------

def profile_blocks(html):
    """{dataset id: parsed JSON} for every profile script block on the page."""
    found = re.findall(r'<script id="profile-(\d+)" type="application/json">(.*?)</script>', html, re.S)
    return {int(pk): json.loads(text) for pk, text in found}


def test_the_profile_is_written_as_json_the_script_can_parse(student_client):
    client, user = student_client
    dataset = make_dataset(user, 'awkward.csv', AWKWARD_PROFILE)
    html = client.get('/datasets/').content.decode()
    assert profile_blocks(html) == {dataset.pk: AWKWARD_PROFILE}


def test_text_that_looks_like_html_cannot_break_out_of_the_data_block(student_client):
    client, user = student_client
    make_dataset(user, 'awkward.csv', AWKWARD_PROFILE)
    html = client.get('/datasets/').content.decode()
    assert '</script><b>' not in html            # json_script escapes < and > inside the data


def test_every_dataset_gets_its_own_block_and_button(student_client):
    client, user = student_client
    first = make_dataset(user, 'one.csv', {'preview': [['1']], 'columns': [{'name': 'a', 'type': 'n', 'missing_values': 0}]})
    second = make_dataset(user, 'two.csv', {'preview': [['2']], 'columns': [{'name': 'b', 'type': 'n', 'missing_values': 0}]})
    html = client.get('/datasets/').content.decode()
    assert set(profile_blocks(html)) == {first.pk, second.pk}
    for dataset in (first, second):
        assert f'data-preview-source="profile-{dataset.pk}"' in html


def test_the_old_attribute_that_could_not_be_parsed_is_gone(student_client):
    client, user = student_client
    make_dataset(user, 'one.csv', AWKWARD_PROFILE)
    html = client.get('/datasets/').content.decode()
    assert 'data-preview="' not in html


def test_the_preview_script_reads_the_profile_from_the_json_block():
    from pathlib import Path
    from django.conf import settings
    source = (Path(settings.BASE_DIR) / 'templates' / 'datasets' / 'workspace.html').read_text(encoding='utf-8')
    assert "querySelectorAll('[data-preview-source]')" in source
    assert 'getElementById(button.dataset.previewSource).textContent' in source
    assert '|escapejs' not in source        # the filter itself, not a comment that names it


def test_another_users_dataset_never_appears_on_my_datasets_page(student_client):
    client, user = student_client
    other = get_user_model().objects.create_user('someone_else', 'o@example.com', 'Passw0rd1')
    make_dataset(other, 'not_mine.csv', AWKWARD_PROFILE)
    html = client.get('/datasets/').content.decode()
    assert 'not_mine' not in html and profile_blocks(html) == {}


# ---- Models page: parameters --------------------------------------------------------------------

def template_text(*parts):
    from pathlib import Path
    from django.conf import settings
    return Path(settings.BASE_DIR, 'templates', *parts).read_text(encoding='utf-8')


def test_a_depth_with_a_value_is_sent_as_a_number_not_text():
    source = template_text('training', 'models.html')
    assert '["int", "int_or_none"].includes(input.dataset.kind)' in source


def test_the_server_refuses_text_and_accepts_numbers_for_the_depth(student_client):
    """The page must send a number: this is why the fix matters."""
    client, _ = student_client

    def validate(depth):
        return client.post('/api/models/decision_tree/params/validate',
                           json.dumps({'params': {'max_depth': depth, 'min_samples_split': 2}}),
                           content_type='application/json')

    assert validate(5).status_code == 200
    assert validate(None).status_code == 200              # empty means "no limit"
    assert validate('5').status_code == 400               # what the page used to send


# ---- Training page: done, and the way to the results ---------------------------------------------

def test_the_training_page_counts_trained_as_finished_and_links_to_the_results():
    source = template_text('training', 'configuration.html')
    assert 'const successStatuses = ["TRAINED", "COMPLETED", "SUCCEEDED"]' in source
    assert '/runs/${encodeURIComponent(runId)}/results/' in source
    assert 'Training done: click to view results' in source


def test_the_training_status_api_reports_trained_not_completed_when_training_ends(student_client):
    """Why the page must accept TRAINED: that is what the status endpoint says once the model is fitted."""
    from experiments.models import Run
    client, user = student_client
    dataset = make_dataset(user, 'one.csv', {})
    run = Run.objects.create(owner=user, dataset=dataset, target_column='label',
                             model_name='knn', status=Run.Status.TRAINED)
    assert client.get(f'/api/train/{run.pk}').json()['status'] == 'TRAINED'


def test_the_results_page_the_button_points_to_exists(student_client):
    from experiments.models import Run
    client, user = student_client
    run = Run.objects.create(owner=user, dataset=make_dataset(user, 'one.csv', {}), target_column='label',
                             model_name='knn', status=Run.Status.TRAINED)
    assert client.get(f'/runs/{run.pk}/results/').status_code == 200


# ---- Dashboard -----------------------------------------------------------------------------------------

def test_the_quick_start_tiles_link_to_the_models_and_evaluation_pages(student_client):
    client, _ = student_client
    html = client.get('/').content.decode()
    assert 'href="/models/"' in html and 'href="/experiments/"' in html
    assert 'Planned' not in html


def test_the_pages_the_dashboard_links_to_open(student_client):
    client, _ = student_client
    for url in ('/datasets/', '/models/', '/experiments/', '/training/'):
        assert client.get(url).status_code == 200, url


# ---- Nothing that is not meant for the user may show on a page ------------------------------------------
# A "{# ... #}" comment must fit on ONE line: if it spans lines Django prints it as text on the page.
# That happened once in the Saved datasets list, so these tests look for it everywhere.

def all_templates():
    from pathlib import Path
    from django.conf import settings
    return sorted(Path(settings.BASE_DIR, 'templates').rglob('*.html'))


def test_no_template_has_a_comment_tag_that_spans_lines():
    broken = [
        f'{path.name}:{number}'
        for path in all_templates()
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1)
        if '{#' in line and '#}' not in line
    ]
    assert broken == [], f'multi-line {{# #}} comments print as text: {broken}'


@pytest.mark.parametrize('url', ['/', '/datasets/', '/models/', '/training/', '/experiments/'])
def test_no_template_code_or_comment_text_leaks_onto_the_pages(student_client, url):
    client, user = student_client
    make_dataset(user, 'iris.csv', {'preview': [['1']], 'columns': [{'name': 'a', 'type': 'n', 'missing_values': 0}]})
    html = client.get(url).content.decode()
    for leaked in ('{#', '#}', '{%', '%}', '{{', '}}'):
        assert leaked not in html, f'{leaked!r} leaked onto {url}'


def test_the_results_and_admin_pages_do_not_leak_template_code_either(client):
    from accounts.models import Role
    from experiments.models import Run
    user = get_user_model().objects.create_user('leak_student', 'l@example.com', 'Passw0rd1')
    admin = get_user_model().objects.create_user('leak_admin', 'a@example.com', 'Passw0rd1')
    admin.profile.role = Role.ADMIN
    admin.profile.save()
    run = Run.objects.create(owner=user, dataset=make_dataset(user, 'x.csv', {}), target_column='t',
                             model_name='knn', status=Run.Status.TRAINED)
    for account, url in ((user, f'/runs/{run.pk}/results/'), (admin, '/accounts/admin-dashboard/')):
        client.force_login(account)
        html = client.get(url).content.decode()
        for leaked in ('{#', '#}', '{%', '%}', '{{', '}}'):
            assert leaked not in html, f'{leaked!r} leaked onto {url}'


def test_the_saved_datasets_list_holds_only_the_dataset_details(student_client):
    client, user = student_client
    make_dataset(user, 'iris.csv', AWKWARD_PROFILE)
    html = client.get('/datasets/').content.decode()
    saved = html.split('id="saved-list"')[1].split('id="saved-preview"')[0]
    assert 'JSON.parse cannot read' not in saved and 'escapejs' not in saved


def test_the_decorative_asterisk_glyphs_are_gone_from_every_template():
    for path in all_templates():
        text = path.read_text(encoding='utf-8')
        for glyph in ('✳', '✦'):
            assert glyph not in text, f'{glyph} is still in {path.name}'
