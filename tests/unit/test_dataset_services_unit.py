"""US-11 unit tests: Data Workspace services (MLE-F-003 to F-006, MLE-SR-003; SAD 4.1.2).

Covers ``datasets.services``: profile_csv, upload_dataset, preprocess_dataframe
and split_dataset, including the Test Plan boundary values for the test share.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from datasets import services
from datasets.errors import ApiValidationError, Unprocessable
from datasets.models import Dataset


@pytest.fixture(autouse=True)
def data_root(settings, tmp_path):
    settings.DATA_ROOT = tmp_path / 'data'
    return settings.DATA_ROOT


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user('unit_user', 'u@example.com', 'Passw0rd1')


def good_csv(rows=25):
    return b'age,city,score\n' + b'20,Pune,1.5\n' * rows


def upload(content=None, name='people.csv'):
    return SimpleUploadedFile(name, good_csv() if content is None else content, content_type='text/csv')


def stored_files(root):
    return sorted(p for p in Path(root).rglob('*') if p.is_file())


# ---- profile_csv (MLE-F-004) -------------------------------------------------

def test_profile_detects_types_and_counts_missing_values(tmp_path):
    path = tmp_path / 'p.csv'
    path.write_text('age,city,ratio,empty\n20,Pune,inf,\n,Delhi,0.5,\n30,,1e3,\n', encoding='utf-8')
    profile = services.profile_csv(path)
    columns = {c['name']: c for c in profile['columns']}
    assert columns['age'] == {'name': 'age', 'type': 'numeric', 'missing_values': 1}
    assert columns['city'] == {'name': 'city', 'type': 'categorical', 'missing_values': 1}
    assert columns['ratio']['type'] == 'categorical'  # 'inf' is not a finite number
    assert columns['empty'] == {'name': 'empty', 'type': 'categorical', 'missing_values': 3}


def test_profile_preview_has_at_most_20_rows(tmp_path):
    path = tmp_path / 'p.csv'
    path.write_bytes(good_csv(rows=30))
    profile = services.profile_csv(path)
    assert len(profile['preview']) == 20
    assert profile['preview'][0] == ['20', 'Pune', '1.5']


# ---- upload_dataset (MLE-F-003, MLE-SR-003) -----------------------------------

def test_upload_stores_the_file_outside_the_web_root_with_a_server_name(user, data_root):
    dataset = services.upload_dataset(user, upload())
    path = Path(dataset.file_path)
    assert path.parent == data_root / str(user.id) / 'datasets'
    assert path.suffix == '.csv' and path.stem != 'people' and len(path.stem) == 32
    assert path.read_bytes() == good_csv()
    assert (dataset.owner, dataset.name, dataset.rows, dataset.columns) == (user, 'people.csv', 25, 3)
    assert dataset.size_bytes == len(good_csv())
    assert [c['name'] for c in dataset.profile_json['columns']] == ['age', 'city', 'score']


def test_display_name_keeps_only_the_file_name(user):
    dataset = services.upload_dataset(user, upload(), display_name='../../etc/passwd.csv')
    assert dataset.name == 'passwd.csv'


def test_long_display_name_is_cut_to_255_characters(user):
    dataset = services.upload_dataset(user, upload(), display_name='x' * 300 + '.csv')
    assert len(dataset.name) == 255


def test_invalid_file_stores_nothing(user, data_root):
    with pytest.raises(ApiValidationError):
        services.upload_dataset(user, upload(b'a,b\n1,2\n'))
    assert not Dataset.objects.exists()
    assert stored_files(data_root) == []


def test_failure_after_storing_removes_the_file(user, data_root, monkeypatch):
    def broken_profile(path):
        raise OSError('disk problem')

    monkeypatch.setattr(services, 'profile_csv', broken_profile)
    with pytest.raises(OSError):
        services.upload_dataset(user, upload())
    assert not Dataset.objects.exists()
    assert stored_files(data_root) == []


def test_twenty_datasets_per_user_then_422(user):
    for _ in range(services.MAX_DATASETS_PER_USER):
        services.upload_dataset(user, upload())
    with pytest.raises(Unprocessable) as exc:
        services.upload_dataset(user, upload())
    assert exc.value.status == 422
    assert 'already have 20 stored datasets' in exc.value.message
    assert Dataset.objects.filter(owner=user).count() == 20


def test_limit_is_per_user(user):
    other = get_user_model().objects.create_user('unit_other', 'o@example.com', 'Passw0rd1')
    for _ in range(services.MAX_DATASETS_PER_USER):
        services.upload_dataset(user, upload())
    assert services.upload_dataset(other, upload()).owner == other


# ---- preprocess_dataframe (MLE-F-005) -----------------------------------------

@pytest.fixture
def frame():
    return pd.DataFrame({
        'age': [20.0, np.nan, 40.0, 100.0],
        'city': ['Pune', 'Delhi', None, 'Pune'],
        'label': ['y', 'n', 'y', 'n'],
    })


@pytest.mark.parametrize('bad', [None, [1, 2], {'a': [1]}])
def test_preprocess_needs_a_dataframe(bad):
    with pytest.raises(ValueError, match='must be a pandas DataFrame'):
        services.preprocess_dataframe(bad, 'mean')


def test_preprocess_refuses_an_empty_frame():
    with pytest.raises(ValueError, match='must contain rows and columns'):
        services.preprocess_dataframe(pd.DataFrame(), 'mean')


def test_preprocess_refuses_an_unknown_strategy(frame):
    with pytest.raises(ValueError, match='Unsupported strategy'):
        services.preprocess_dataframe(frame, 'zero')


@pytest.mark.parametrize('strategy, age', [('mean', 160 / 3), ('median', 40.0)])
def test_numeric_fill_strategies(frame, strategy, age):
    result = services.preprocess_dataframe(frame, strategy)
    assert result.loc[1, 'age'] == pytest.approx(age)
    assert result.loc[2, 'city_Pune'] == 1  # text is filled with the most frequent value


def test_most_frequent_fills_every_column(frame):
    result = services.preprocess_dataframe(frame, 'most_frequent')
    assert not result.isna().any().any()
    assert result.loc[1, 'age'] == 20.0


def test_drop_rows_removes_incomplete_rows(frame):
    result = services.preprocess_dataframe(frame, 'drop_rows')
    assert len(result) == 2
    assert list(result.index) == [0, 1]


def test_one_hot_columns_are_integers_and_the_input_is_unchanged(frame):
    before = frame.copy()
    result = services.preprocess_dataframe(frame, 'median')
    assert {'city_Delhi', 'city_Pune', 'label_n', 'label_y'} <= set(result.columns)
    assert result['city_Pune'].dtype.kind == 'i'
    pd.testing.assert_frame_equal(frame, before)


def test_numeric_only_frame_has_no_one_hot_columns():
    result = services.preprocess_dataframe(pd.DataFrame({'a': [1.0, None], 'b': [3, 4]}), 'mean')
    assert list(result.columns) == ['a', 'b']


@pytest.mark.parametrize('strategy', ['mean', 'median'])
def test_numeric_column_with_only_missing_values_is_refused(strategy):
    frame = pd.DataFrame({'a': [np.nan, np.nan], 'b': [1.0, 2.0]})
    with pytest.raises(ValueError, match="Column 'a' contains only missing values"):
        services.preprocess_dataframe(frame, strategy)


def test_text_column_with_only_missing_values_is_refused():
    frame = pd.DataFrame({'a': [None, None], 'b': [1.0, 2.0]}, dtype=object)
    with pytest.raises(ValueError, match="Column 'a' contains only missing values"):
        services.preprocess_dataframe(frame, 'most_frequent')


def test_drop_rows_that_removes_everything_is_refused():
    with pytest.raises(ValueError, match='removed all rows'):
        services.preprocess_dataframe(pd.DataFrame({'a': [1, None], 'b': [None, 2]}), 'drop_rows')


# ---- split_dataset (MLE-F-006) -------------------------------------------------

def classes_frame(n_per_class=10, classes=('a', 'b')):
    labels = [c for c in classes for _ in range(n_per_class)]
    return pd.DataFrame({'x': range(len(labels)), 'y': labels})


@pytest.mark.parametrize('test_size', [0.10, 0.15, 0.2, 0.35, 0.50])
def test_test_share_from_10_to_50_percent_in_steps_of_5_is_accepted(test_size):
    X_train, X_test, _, _ = services.split_dataset(classes_frame(20), 'y', test_size, 1)
    assert len(X_test) == round(40 * test_size)


@pytest.mark.parametrize('test_size', [0.05, 0.09, 0.51, 0.55, 0.12, 0, 1, True, '0.2', float('nan'), float('inf')])
def test_other_test_shares_are_refused(test_size):
    with pytest.raises(ValueError, match='Test size must be from 10% to 50% in steps of 5%'):
        services.split_dataset(classes_frame(), 'y', test_size, 1)


@pytest.mark.xfail(strict=True, reason='Defect D-1: 0.151 is rounded to 15% and accepted')
def test_share_that_is_not_a_whole_5_percent_step_is_refused():
    with pytest.raises(ValueError):
        services.split_dataset(classes_frame(20), 'y', 0.151, 1)


@pytest.mark.parametrize('seed', [1.5, '42', True, None])
def test_random_seed_must_be_an_integer(seed):
    with pytest.raises(ValueError, match='Random seed must be an integer'):
        services.split_dataset(classes_frame(), 'y', 0.2, seed)


def test_split_refuses_a_missing_target_column():
    with pytest.raises(ValueError, match='Target column does not exist'):
        services.split_dataset(classes_frame(), 'nope', 0.2, 1)


def test_split_refuses_missing_target_values():
    frame = classes_frame()
    frame.loc[0, 'y'] = None
    with pytest.raises(ValueError, match='must not contain missing values'):
        services.split_dataset(frame, 'y', 0.2, 1)


@pytest.mark.parametrize('n_classes', [2, 20])
def test_two_to_twenty_classes_are_accepted(n_classes):
    frame = classes_frame(5, tuple(f'c{i}' for i in range(n_classes)))
    services.split_dataset(frame, 'y', 0.5, 1)


@pytest.mark.parametrize('n_classes', [1, 21])
def test_one_or_twenty_one_classes_are_refused(n_classes):
    frame = classes_frame(5, tuple(f'c{i}' for i in range(n_classes)))
    with pytest.raises(ValueError, match='between 2 and 20 classes'):
        services.split_dataset(frame, 'y', 0.2, 1)


def test_class_with_a_single_row_is_refused():
    frame = pd.concat([classes_frame(), pd.DataFrame({'x': [99], 'y': ['z']})])
    with pytest.raises(ValueError, match='at least 2 rows'):
        services.split_dataset(frame, 'y', 0.2, 1)


def test_split_is_stratified_repeatable_and_drops_the_target():
    frame = classes_frame(n_per_class=30, classes=('a', 'b', 'c'))
    first = services.split_dataset(frame, 'y', 0.2, 7)
    again = services.split_dataset(frame, 'y', 0.2, 7)
    X_train, X_test, y_train, y_test = first
    assert list(X_test.index) == list(again[1].index)
    assert y_test.value_counts().to_dict() == {'a': 6, 'b': 6, 'c': 6}
    assert 'y' not in X_train.columns


def test_split_that_cannot_be_stratified_is_explained():
    with pytest.raises(ValueError, match='Cannot create a stratified split'):
        services.split_dataset(classes_frame(2, ('a', 'b', 'c')), 'y', 0.1, 1)


@pytest.mark.parametrize('bad', [None, pd.DataFrame()])
def test_split_needs_a_non_empty_dataframe(bad):
    with pytest.raises(ValueError):
        services.split_dataset(bad, 'y', 0.2, 1)
