"""US-07 / MLE-F-008: POST /api/models/<key>/params/validate (SAD 4.3.1, 4.4.2)."""
import json

import pytest

pytestmark = pytest.mark.django_db


def url(key):
    return f'/api/models/{key}/params/validate'


def post(client, key, payload):
    return client.post(url(key), data=json.dumps(payload), content_type='application/json')


@pytest.fixture
def student_client(client, student):
    client.force_login(student)
    return client


def test_anonymous_user_gets_401(client):
    response = post(client, 'knn', {'params': {}})
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'AUTH_REQUIRED'


def test_admin_is_forbidden(client, admin_user):
    client.force_login(admin_user)
    response = post(client, 'knn', {'params': {}})
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'FORBIDDEN'


@pytest.mark.parametrize('who', ['student', 'scientist'])
def test_valid_params_return_the_complete_set(client, request, who):
    client.force_login(request.getfixturevalue(who))
    response = post(client, 'logistic_regression', {'params': {'C': 2.5}})
    assert response.status_code == 200
    assert response.json() == {
        'valid': True,
        'model': 'logistic_regression',
        'params': {'C': 2.5, 'max_iter': 200},
    }


def test_missing_params_give_the_defaults(student_client):
    response = post(student_client, 'random_forest', {})
    assert response.status_code == 200
    assert response.json()['params'] == {'n_estimators': 100, 'max_depth': None}


def test_negative_c_is_refused_naming_the_parameter_and_range(student_client):
    # TC-MODEL-01 test data: C = -5 must be refused before training starts.
    response = post(student_client, 'logistic_regression', {'params': {'C': -5}})
    assert response.status_code == 400
    error = response.json()['error']
    assert error['code'] == 'VALIDATION_ERROR'
    assert error['message'] == 'C must be a number between 0.01 and 100.'
    assert error['details']['field'] == 'params.C'
    assert error['details']['errors'] == [
        {'field': 'params.C', 'message': 'C must be a number between 0.01 and 100.'}
    ]


def test_every_problem_is_reported_in_one_response(student_client):
    response = post(student_client, 'knn', {'params': {'n_neighbors': 0, 'weights': 'x'}})
    assert response.status_code == 400
    fields = [e['field'] for e in response.json()['error']['details']['errors']]
    assert fields == ['params.n_neighbors', 'params.weights']


def test_params_that_are_not_an_object_are_refused(student_client):
    response = post(student_client, 'knn', {'params': [1, 2]})
    assert response.status_code == 400
    assert response.json()['error']['details']['field'] == 'params'


def test_unknown_model_is_404(student_client):
    response = post(student_client, 'svm', {'params': {}})
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'NOT_FOUND'


@pytest.mark.parametrize('body', ['{not json', '[1, 2]', b'\xff\xfe'])
def test_body_that_is_not_a_json_object_is_400(student_client, body):
    response = student_client.post(url('knn'), data=body, content_type='application/json')
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'VALIDATION_ERROR'


def test_get_is_not_allowed(student_client):
    response = student_client.get(url('knn'))
    assert response.status_code == 405
    assert response.json()['error']['code'] == 'METHOD_NOT_ALLOWED'
