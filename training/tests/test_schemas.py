"""US-08: validation of the POST /api/train body (SAD 4.3.4)."""
import pytest

from training.schemas import parse_train_request

VALID = {'dataset_id': 7, 'target_column': 'label', 'model': 'random_forest'}


def fields(body):
    parsed, errors = parse_train_request(body)
    assert parsed is None
    return {e['field'] for e in errors}


def test_minimal_body_gets_the_sad_defaults():
    parsed, errors = parse_train_request(VALID)
    assert errors == []
    assert parsed.dataset_id == 7
    assert parsed.params == {'n_estimators': 100, 'max_depth': None}
    assert parsed.preprocessing == {'missing': 'median', 'categorical': 'one_hot'}
    assert parsed.split == {'test_size': 0.2, 'random_state': 42}


def test_full_sad_example_body_is_accepted():
    body = {
        'dataset_id': 7,
        'target_column': 'survived',
        'model': 'random_forest',
        'params': {'n_estimators': 100, 'max_depth': 8},
        'preprocessing': {'missing': 'mean', 'categorical': 'one_hot'},
        'split': {'test_size': 0.3, 'random_state': 1},
    }
    parsed, errors = parse_train_request(body)
    assert errors == []
    assert parsed.params == {'n_estimators': 100, 'max_depth': 8}
    assert parsed.split == {'test_size': 0.3, 'random_state': 1}


@pytest.mark.parametrize('value', [None, 0, -1, '7', 1.5, True])
def test_bad_dataset_id(value):
    assert fields({**VALID, 'dataset_id': value}) == {'dataset_id'}


@pytest.mark.parametrize('value', [None, '', '   ', 5, 'x' * 201])
def test_bad_target_column(value):
    assert fields({**VALID, 'target_column': value}) == {'target_column'}


@pytest.mark.parametrize('value', [None, 'svm', 3])
def test_unknown_model(value):
    assert fields({**VALID, 'model': value}) == {'model'}


def test_out_of_range_params_are_reported_per_parameter():
    assert fields({**VALID, 'params': {'n_estimators': 5, 'max_depth': 0}}) == {
        'params.n_estimators', 'params.max_depth'}


@pytest.mark.parametrize('value', [0.05, 0.55, 0.23, '0.2', None, True, float('nan')])
def test_bad_test_size(value):
    assert fields({**VALID, 'split': {'test_size': value}}) == {'split.test_size'}


@pytest.mark.parametrize('value', [0.1, 0.15, 0.25, 0.5])
def test_good_test_size(value):
    assert parse_train_request({**VALID, 'split': {'test_size': value}})[1] == []


@pytest.mark.parametrize('value', [-1, 2**31, 1.5, '42', None])
def test_bad_random_state(value):
    assert fields({**VALID, 'split': {'random_state': value}}) == {'split.random_state'}


def test_bad_preprocessing_options():
    assert fields({**VALID, 'preprocessing': {'missing': 'zero'}}) == {'preprocessing.missing'}
    assert fields({**VALID, 'preprocessing': {'categorical': 'label'}}) == {'preprocessing.categorical'}
    assert fields({**VALID, 'preprocessing': {'scale': True}}) == {'preprocessing'}


def test_unknown_split_setting():
    assert fields({**VALID, 'split': {'shuffle': False}}) == {'split'}


@pytest.mark.parametrize('name', ['preprocessing', 'split'])
def test_sections_must_be_objects(name):
    assert fields({**VALID, name: [1]}) == {name}


def test_every_problem_is_reported_together():
    assert fields({'model': 'svm', 'split': {'test_size': 2}}) == {
        'dataset_id', 'target_column', 'model', 'split.test_size'}
