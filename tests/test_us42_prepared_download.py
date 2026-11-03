"""US-42: GET /api/datasets/<id>/prepared downloads a prepared copy (MLE-F-005, MLE-SR-003, MLE-SR-005)."""
import io
import json

import pandas as pd
import pytest
from django.contrib.auth import get_user_model

from accounts.models import Role
from audit.models import Action, AuditLog
from datasets.models import Dataset

pytestmark = pytest.mark.django_db

User = get_user_model()

# age is missing in row 2, height in row 1, colour in row 2.
#   median age [1,2,4] = 2     mean age = 7/3        most frequent age = 1 (ties give the smallest)
#   median height [10,30,40] = 30   mean = 80/3      most frequent height = 10
#   colour: red twice, blue once -> red
RAW = 'age,height,colour,label\n1,10,red,a\n2,,blue,b\n,30,,a\n4,40,red,b\n'


def make_user(name, role):
    user = User.objects.create_user(name, f'{name}@example.com', 'Passw0rd1')
    user.profile.role = role
    user.profile.save()
    return user


@pytest.fixture
def owner(db):
    return make_user('owner_u', Role.STUDENT)


@pytest.fixture
def stranger(db):
    return make_user('stranger_u', Role.DATA_SCIENTIST)


@pytest.fixture
def admin_user(db):
    return make_user('admin_dl', Role.ADMIN)


def make_dataset(user, tmp_path, text=RAW, name='iris.csv'):
    path = tmp_path / f'{user.pk}_{abs(hash(text)) % 10**8}.csv'
    path.write_text(text, encoding='utf-8')
    return Dataset.objects.create(owner=user, name=name, file_path=str(path), size_bytes=path.stat().st_size,
                                  rows=4, columns=4, profile_json={})


@pytest.fixture
def dataset(owner, tmp_path):
    return make_dataset(owner, tmp_path)


def download(client, dataset, **query):
    return client.get(f'/api/datasets/{dataset.pk}/prepared', query)


def frame(response):
    assert response.status_code == 200, response.content[:300]
    return pd.read_csv(io.BytesIO(response.content))


# ---- the content, worked out by hand -------------------------------------------------------------

def test_median_fills_numbers_with_the_median_and_text_with_the_most_common_value(client, owner, dataset):
    client.force_login(owner)
    result = frame(download(client, dataset, strategy='median'))
    assert list(result.columns) == ['age', 'height', 'colour_blue', 'colour_red', 'label_a', 'label_b']
    assert result.age.tolist() == [1.0, 2.0, 2.0, 4.0]            # median of 1, 2, 4 is 2
    assert result.height.tolist() == [10.0, 30.0, 30.0, 40.0]     # median of 10, 30, 40 is 30
    assert result.colour_red.tolist() == [1, 0, 1, 1]             # the missing colour became red
    assert result.colour_blue.tolist() == [0, 1, 0, 0]
    assert result.label_a.tolist() == [1, 0, 1, 0]


def test_the_median_strategy_is_the_default(client, owner, dataset):
    client.force_login(owner)
    assert frame(download(client, dataset)).equals(frame(download(client, dataset, strategy='median')))


def test_mean_fills_with_the_average(client, owner, dataset):
    client.force_login(owner)
    result = frame(download(client, dataset, strategy='mean'))
    assert result.age.tolist() == pytest.approx([1.0, 2.0, 7 / 3, 4.0])
    assert result.height.tolist() == pytest.approx([10.0, 80 / 3, 30.0, 40.0])


def test_most_frequent_fills_with_the_most_common_value(client, owner, dataset):
    client.force_login(owner)
    result = frame(download(client, dataset, strategy='most_frequent'))
    assert result.age.tolist() == [1.0, 2.0, 1.0, 4.0]            # 1, 2, 4 tie, the smallest wins
    assert result.height.tolist() == [10.0, 10.0, 30.0, 40.0]


def test_drop_rows_removes_every_row_with_a_missing_value(client, owner, dataset):
    client.force_login(owner)
    result = frame(download(client, dataset, strategy='drop_rows'))
    assert len(result) == 2                                       # only rows 0 and 3 are complete
    assert result.age.tolist() == [1, 4]
    assert result.height.tolist() == [10, 40]
    assert 'colour_blue' not in result.columns                    # blue only appeared in a dropped row


def test_no_missing_value_is_left_in_the_download(client, owner, dataset):
    client.force_login(owner)
    for strategy in ('mean', 'median', 'most_frequent', 'drop_rows'):
        assert not frame(download(client, dataset, strategy=strategy)).isna().any().any(), strategy


# ---- keeping one column as it is -----------------------------------------------------------------------------

def test_a_kept_column_stays_exactly_as_it_was(client, owner, dataset):
    client.force_login(owner)
    result = frame(download(client, dataset, strategy='median', keep='label'))
    assert list(result.columns) == ['age', 'height', 'colour_blue', 'colour_red', 'label']
    assert result.label.tolist() == ['a', 'b', 'a', 'b']          # not turned into label_a / label_b


def test_a_kept_column_stays_lined_up_when_rows_are_dropped(client, owner, dataset):
    client.force_login(owner)
    result = frame(download(client, dataset, strategy='drop_rows', keep='label'))
    assert result.age.tolist() == [1, 4] and result.label.tolist() == ['a', 'b']


def test_a_kept_column_with_missing_values_is_left_with_them(client, owner, tmp_path):
    client.force_login(owner)
    dataset = make_dataset(owner, tmp_path, 'x,label\n1,a\n2,\n3,b\n', name='gaps.csv')
    result = frame(download(client, dataset, strategy='median', keep='label'))
    assert result.label.isna().tolist() == [False, True, False]   # kept as it was, not filled in


def test_keeping_a_column_that_does_not_exist_is_refused(client, owner, dataset):
    client.force_login(owner)
    response = download(client, dataset, keep='nope')
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'VALIDATION_ERROR'


def test_keeping_the_only_column_is_refused_with_a_reason(client, owner, tmp_path):
    client.force_login(owner)
    dataset = make_dataset(owner, tmp_path, 'only\n1\n2\n3\n', name='one.csv')
    response = download(client, dataset, keep='only')
    assert response.status_code == 400
    assert 'nothing to prepare' in response.json()['error']['message']


# ---- the original is never touched -----------------------------------------------------------------------------

def test_the_stored_dataset_is_not_changed(client, owner, dataset):
    client.force_login(owner)
    from pathlib import Path
    before = Path(dataset.file_path).read_bytes()
    download(client, dataset, strategy='drop_rows')
    assert Path(dataset.file_path).read_bytes() == before
    assert Dataset.objects.count() == 1


# ---- the file itself ----------------------------------------------------------------------------------------------

def test_it_is_sent_as_a_csv_download(client, owner, dataset):
    client.force_login(owner)
    response = download(client, dataset)
    assert response['Content-Type'].startswith('text/csv')
    assert response['Content-Disposition'] == 'attachment; filename="iris-prepared.csv"'


@pytest.mark.parametrize('name,expected', [
    ('My data (final)!.csv', 'My_data_final-prepared.csv'),
    ('../../etc/passwd', 'passwd-prepared.csv'),
    ('a"b;c.csv', 'a_b_c-prepared.csv'),
    ('...', 'dataset-prepared.csv'),
    ('naïve ✓.csv', 'na_ve-prepared.csv'),
])
def test_the_download_name_is_made_safe(client, owner, tmp_path, name, expected):
    client.force_login(owner)
    dataset = make_dataset(owner, tmp_path, name=name)
    assert download(client, dataset)['Content-Disposition'] == f'attachment; filename="{expected}"'


# ---- spreadsheet formulas (MLE-SR-003) ------------------------------------------------------------------------------

FORMULAS = '=evil,name,score\n1,=HYPERLINK("http://x"),-5\n2,@bad,3\n3, +cmd,4\n4,fine,5\n'


def test_text_that_looks_like_a_formula_is_neutralised_and_numbers_are_not(client, owner, tmp_path):
    client.force_login(owner)
    dataset = make_dataset(owner, tmp_path, FORMULAS, name='formulas.csv')
    result = frame(download(client, dataset, keep='name'))
    assert result.name.tolist() == ['\'=HYPERLINK("http://x")', "'@bad", "' +cmd", 'fine']
    assert result.score.tolist() == [-5, 3, 4, 5]                 # -5 is still a number, not "'-5"


def test_a_column_name_that_looks_like_a_formula_is_neutralised(client, owner, tmp_path):
    client.force_login(owner)
    dataset = make_dataset(owner, tmp_path, FORMULAS, name='formulas.csv')
    header = download(client, dataset, keep='name').content.decode().splitlines()[0]
    assert header.startswith("'=evil,")


# ---- who may download -------------------------------------------------------------------------------------------------

def test_a_visitor_gets_401(client, dataset):
    assert download(client, dataset).status_code == 401


def test_the_admin_cannot_download_anyones_data(client, admin_user, dataset):
    """SRS Table 4.1-1: the Admin manages dataset records, never their contents."""
    client.force_login(admin_user)
    response = download(client, dataset)
    assert response.status_code == 403
    assert b'red' not in response.content


def test_someone_elses_dataset_is_the_same_404_as_a_missing_one(client, stranger, dataset):
    client.force_login(stranger)
    theirs = download(client, dataset)

    class Missing:
        pk = 999999
    missing = download(client, Missing)
    assert theirs.status_code == missing.status_code == 404
    assert theirs.json()['error']['message'] == missing.json()['error']['message']
    assert b'red' not in theirs.content


def test_only_get_is_allowed(client, owner, dataset):
    client.force_login(owner)
    assert client.post(f'/api/datasets/{dataset.pk}/prepared').status_code == 405


# ---- bad requests ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('strategy', ['average', 'MEAN', '1', 'drop rows'])
def test_an_unknown_strategy_is_refused(client, owner, dataset, strategy):
    client.force_login(owner)
    response = download(client, dataset, strategy=strategy)
    assert response.status_code == 400
    assert response.json()['error']['details']['field'] == 'strategy'


def test_a_file_that_has_gone_is_reported_not_a_crash(client, owner, dataset):
    from pathlib import Path
    Path(dataset.file_path).unlink()
    client.force_login(owner)
    response = download(client, dataset)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'UNPROCESSABLE'


def test_a_column_with_only_missing_values_is_reported_with_its_name(client, owner, tmp_path):
    client.force_login(owner)
    dataset = make_dataset(owner, tmp_path, 'a,b\n1,\n2,\n3,\n', name='empty_col.csv')
    response = download(client, dataset, strategy='median')
    assert response.status_code == 400
    assert "'b'" in response.json()['error']['message']


# ---- the audit log (MLE-SR-005) -----------------------------------------------------------------------------------------------

def test_a_download_is_logged_with_user_and_dataset_but_no_data(client, owner, dataset):
    client.force_login(owner)
    AuditLog.objects.all().delete()
    download(client, dataset)
    entry = AuditLog.objects.get(action=Action.REPORT_EXPORT)
    assert entry.user == owner and entry.target == f'dataset:{dataset.pk}' and entry.ip_address == '127.0.0.1'
    stored = json.dumps(list(AuditLog.objects.values()), default=str)
    assert 'iris' not in stored and 'colour' not in stored


def test_a_refused_download_is_not_logged_as_a_download(client, stranger, admin_user, dataset):
    for user in (stranger, admin_user):
        client.force_login(user)
        download(client, dataset)
    assert not AuditLog.objects.filter(action=Action.REPORT_EXPORT).exists()


def test_trying_to_download_someone_elses_dataset_is_logged_as_denied(client, stranger, dataset):
    client.force_login(stranger)
    AuditLog.objects.all().delete()
    download(client, dataset)
    entry = AuditLog.objects.get(action=Action.ACCESS_DENIED)
    assert entry.user == stranger and entry.target == f'dataset:{dataset.pk}'


def test_asking_for_a_dataset_that_does_not_exist_is_not_logged(client, stranger, dataset):
    client.force_login(stranger)
    AuditLog.objects.all().delete()
    client.get('/api/datasets/999999/prepared')
    assert AuditLog.objects.count() == 0


# ---- the Datasets page ---------------------------------------------------------------------------------------------------------

PROFILE = {'preview': [], 'columns': [{'name': 'age', 'type': 'numeric', 'missing_values': 1},
                                      {'name': 'label', 'type': 'text', 'missing_values': 0}]}


def page(client, user):
    client.force_login(user)
    return client.get('/datasets/').content.decode()


def test_each_saved_dataset_has_a_download_form_pointing_at_the_download(client, owner, tmp_path):
    first = make_dataset(owner, tmp_path, RAW, name='one.csv')
    second = make_dataset(owner, tmp_path, 'a,b\n1,x\n', name='two.csv')
    html = page(client, owner)
    for dataset in (first, second):
        assert f'action="/api/datasets/{dataset.pk}/prepared"' in html


def test_the_form_offers_the_four_strategies_and_the_datasets_columns(client, owner, tmp_path):
    dataset = make_dataset(owner, tmp_path, RAW, name='one.csv')
    Dataset.objects.filter(pk=dataset.pk).update(profile_json=PROFILE)
    html = page(client, owner)
    for strategy in ('median', 'mean', 'most_frequent', 'drop_rows'):
        assert f'<option value="{strategy}">' in html
    assert '<option value="age">age</option>' in html and '<option value="label">label</option>' in html
    assert 'name="strategy"' in html and 'name="keep"' in html


def test_awkward_column_names_are_escaped_in_the_form(client, owner, tmp_path):
    dataset = make_dataset(owner, tmp_path, RAW, name='one.csv')
    Dataset.objects.filter(pk=dataset.pk).update(profile_json={
        'columns': [{'name': '"><script>alert(1)</script>', 'type': 'text', 'missing_values': 0}]})
    html = page(client, owner)
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html


def test_the_form_only_appears_for_your_own_datasets(client, owner, stranger, tmp_path):
    mine = make_dataset(owner, tmp_path, RAW, name='mine.csv')
    theirs = make_dataset(stranger, tmp_path, 'a,b\n1,x\n', name='theirs.csv')
    html = page(client, owner)
    assert f'/api/datasets/{mine.pk}/prepared' in html
    assert f'/api/datasets/{theirs.pk}/prepared' not in html and 'theirs.csv' not in html


def test_a_dataset_without_a_profile_still_gets_a_working_form(client, owner, tmp_path):
    dataset = make_dataset(owner, tmp_path, RAW, name='plain.csv')       # profile_json is {}
    html = page(client, owner)
    assert f'action="/api/datasets/{dataset.pk}/prepared"' in html and 'Encode every text column' in html


def test_the_form_really_downloads_what_it_asks_for(client, owner, tmp_path):
    """Submitting the form's own field names gives the file the form promises."""
    dataset = make_dataset(owner, tmp_path, RAW, name='one.csv')
    client.force_login(owner)
    response = client.get(f'/api/datasets/{dataset.pk}/prepared', {'strategy': 'drop_rows', 'keep': ''})
    assert response.status_code == 200 and len(frame(response)) == 2          # keep= empty means "no column kept"


# ---- the protection must not depend on how pandas stores text --------------------------------------------------------
# pandas 2 stores text as "object", pandas 3 (what GitHub installs) as a separate string type. A check for
# "object" alone let formulas through on pandas 3, so every kind of text column is tested directly.

@pytest.mark.parametrize('dtype', ['object', 'string', 'category'])
def test_formula_text_is_neutralised_whatever_type_pandas_stores_it_as(dtype):
    from datasets.prepared_download import neutralise_frame
    frame = pd.DataFrame({'=evil': pd.Series(['=cmd', '+1', ' -x', '@y', 'fine', None], dtype=dtype),
                          'score': [-5, 1, 2, 3, 4, 5]})
    safe = neutralise_frame(frame)
    assert list(safe.columns) == ["'=evil", 'score']
    assert safe.iloc[:, 0].astype(object).tolist() == ["'=cmd", "'+1", "' -x", "'@y", 'fine', '']   # missing -> empty
    assert safe.score.tolist() == [-5, 1, 2, 3, 4, 5]          # numbers stay numbers


@pytest.mark.parametrize('dtype', ['object', 'string', 'category'])
def test_missing_text_is_written_as_an_empty_cell_not_a_marker(dtype):
    from datasets.prepared_download import neutralise_frame
    frame = pd.DataFrame({'t': pd.Series(['a', None], dtype=dtype), 'n': [1, 2]})
    lines = neutralise_frame(frame).to_csv(index=False).splitlines()
    assert lines == ['t,n', 'a,1', ',2']                        # an empty cell, never <NA>, nan or None


def test_safe_cell_handles_every_kind_of_missing_value():
    from datasets.prepared_download import safe_cell
    for missing in (None, float('nan'), pd.NA):
        assert safe_cell(missing) == ''


def test_two_columns_that_end_up_with_the_same_name_are_both_cleaned():
    from datasets.prepared_download import neutralise_frame
    frame = pd.DataFrame([['=a', '=b']], columns=['x', 'x'])
    safe = neutralise_frame(frame)
    assert safe.iloc[0].tolist() == ["'=a", "'=b"]
