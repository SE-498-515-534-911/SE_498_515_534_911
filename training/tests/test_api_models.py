"""US-06 / MLE-F-007: GET /api/models (SAD 4.3.2, 4.3.4, 4.4.2)."""
import pytest

pytestmark = pytest.mark.django_db

URL = '/api/models'


def test_anonymous_user_gets_401_in_the_standard_envelope(client):
    response = client.get(URL)
    assert response.status_code == 401
    error = response.json()['error']
    assert error['code'] == 'AUTH_REQUIRED'
    assert error['request_id']


@pytest.mark.parametrize('who', ['student', 'scientist'])
def test_data_roles_get_the_catalogue(client, request, who):
    client.force_login(request.getfixturevalue(who))
    response = client.get(URL)
    assert response.status_code == 200
    keys = [m['key'] for m in response.json()['models']]
    assert keys == ['logistic_regression', 'knn', 'decision_tree', 'random_forest']


def test_admin_is_forbidden(client, admin_user):
    client.force_login(admin_user)
    response = client.get(URL)
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'FORBIDDEN'


def test_each_model_carries_defaults_and_parameter_schema(client, student):
    client.force_login(student)
    models = {m['key']: m for m in client.get(URL).json()['models']}
    rf = models['random_forest']
    assert rf['label'] == 'Random Forest'
    assert rf['defaults'] == {'n_estimators': 100, 'max_depth': None}
    n_estimators = next(p for p in rf['params'] if p['name'] == 'n_estimators')
    assert (n_estimators['minimum'], n_estimators['maximum']) == (10, 200)
    assert n_estimators['range'] == 'a whole number between 10 and 200'
    weights = next(p for p in models['knn']['params'] if p['name'] == 'weights')
    assert weights['choices'] == ['uniform', 'distance']


@pytest.mark.parametrize('method', ['post', 'put', 'delete'])
def test_other_methods_are_refused(client, student, method):
    client.force_login(student)
    response = getattr(client, method)(URL)
    assert response.status_code == 405
    assert response.json()['error']['code'] == 'METHOD_NOT_ALLOWED'
