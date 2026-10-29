"""US-38: one user can never reach another user's data (MLE-SR-005(a), SAD DD4, TC-SEC-01).

Every way of asking for Alice's dataset or run, as Bob, must:
* fail with a generic 404, word for word the same answer as for an item that
  does not exist (so it does not reveal that the item exists);
* leak none of Alice's data (names, paths, metrics).
The Admin cannot use data features at all (SRS Table 4.1-1), and a visitor who
is not logged in gets 401 or a redirect to login.
"""
import json

import pytest

from experiments.models import Metric

from .conftest import make_dataset, make_run

pytestmark = pytest.mark.django_db

MISSING = 999999


@pytest.fixture
def private_dataset(alice, tmp_path):
    return make_dataset(alice, tmp_path, name='alice_private_data.csv')


@pytest.fixture
def private_run(alice, private_dataset):
    run = make_run(alice, private_dataset)
    Metric.objects.create(run=run, name='test_accuracy', value=0.8765)
    return run


def error_of(response):
    """What the user is told, without the per-request id."""
    error = response.json()['error']
    return error['code'], error['message']


def post_json(client, url, payload):
    return client.post(url, json.dumps(payload), content_type='application/json')


# ---- a run in the URL --------------------------------------------------------------------

@pytest.mark.parametrize('url', ['/api/train/{id}', '/api/evaluate/{id}'])
def test_someone_elses_run_gets_the_same_answer_as_a_missing_run(client, bob, private_run, url):
    client.force_login(bob)
    theirs = client.get(url.format(id=private_run.pk))
    missing = client.get(url.format(id=MISSING))
    assert theirs.status_code == missing.status_code == 404
    assert error_of(theirs) == error_of(missing)


def test_someone_elses_results_page_is_404(client, bob, private_run):
    client.force_login(bob)
    assert client.get(f'/runs/{private_run.pk}/results/').status_code == 404
    assert client.get(f'/runs/{MISSING}/results/').status_code == 404


@pytest.mark.parametrize('url', ['/api/train/{id}', '/api/evaluate/{id}'])
def test_nothing_of_the_run_leaks_in_the_refusal(client, bob, private_run, url):
    client.force_login(bob)
    text = client.get(url.format(id=private_run.pk)).content.decode()
    for secret in ('logistic_regression', 'label', 'alice_private_data', '0.8765', 'test_accuracy'):
        assert secret not in text


# ---- lists never include other users' items -----------------------------------------------

def test_run_history_lists_only_your_own_runs(client, alice, bob, private_run, tmp_path):
    bobs_run = make_run(bob, make_dataset(bob, tmp_path, name='bobs.csv'))
    client.force_login(bob)
    runs = client.get('/api/runs').json()['runs']
    assert [r['run_id'] for r in runs] == [bobs_run.pk]
    assert 'test_accuracy' not in json.dumps(runs)       # Alice's metric is not in Bob's list


def test_a_user_with_no_runs_sees_an_empty_history_not_other_peoples(client, bob, private_run):
    client.force_login(bob)
    assert client.get('/api/runs').json() == {'runs': []}


@pytest.mark.parametrize('url', ['/', '/datasets/'])
def test_dataset_pages_show_only_your_own_datasets(client, bob, private_dataset, url):
    client.force_login(bob)
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert 'alice_private_data' not in html and private_dataset.file_path not in html


# ---- a dataset id sent in a request ---------------------------------------------------------

def test_training_on_someone_elses_dataset_is_the_same_as_a_missing_dataset(client, bob, private_dataset):
    client.force_login(bob)
    body = {'target_column': 'label', 'model': 'knn'}
    theirs = post_json(client, '/api/train', {**body, 'dataset_id': private_dataset.pk})
    missing = post_json(client, '/api/train', {**body, 'dataset_id': MISSING})
    assert theirs.status_code == missing.status_code == 404
    assert error_of(theirs) == error_of(missing)
    assert 'alice_private_data' not in theirs.content.decode()


def test_no_run_is_created_for_someone_elses_dataset(client, bob, private_dataset):
    from experiments.models import Run
    client.force_login(bob)
    post_json(client, '/api/train', {'dataset_id': private_dataset.pk,
                                     'target_column': 'label', 'model': 'knn'})
    assert not Run.objects.filter(owner=bob).exists()


def test_preprocessing_someone_elses_dataset_is_the_same_as_a_missing_dataset(client, bob, private_dataset):
    client.force_login(bob)
    theirs = client.post('/api/datasets/preprocess',
                         {'dataset_id': private_dataset.pk, 'strategy': 'drop_missing'})
    missing = client.post('/api/datasets/preprocess',
                          {'dataset_id': MISSING, 'strategy': 'drop_missing'})
    assert theirs.status_code == missing.status_code == 404
    assert theirs.json()['error']['message'] == missing.json()['error']['message']


# ---- the model file ---------------------------------------------------------------------------

def test_another_users_model_file_cannot_be_loaded(alice, bob, tmp_path, settings):
    from sklearn.linear_model import LogisticRegression
    from training.artifacts import ArtifactError, load_artifact, save_artifact
    settings.MODEL_ARTIFACT_ROOT = tmp_path / 'artifacts'
    artifact = save_artifact(alice, LogisticRegression())
    with pytest.raises(ArtifactError, match='another user'):
        load_artifact(bob, artifact)


# ---- the Admin and visitors -----------------------------------------------------------------------

@pytest.mark.parametrize('url', ['/api/train/{id}', '/api/evaluate/{id}', '/api/runs', '/runs/{id}/results/'])
def test_the_admin_cannot_read_anyones_runs(client, admin_user, private_run, url):
    client.force_login(admin_user)
    response = client.get(url.format(id=private_run.pk))
    assert response.status_code == 403
    assert 'test_accuracy' not in response.content.decode()


def test_the_admin_cannot_train_on_a_users_dataset(client, admin_user, private_dataset):
    client.force_login(admin_user)
    response = post_json(client, '/api/train', {'dataset_id': private_dataset.pk,
                                                'target_column': 'label', 'model': 'knn'})
    assert response.status_code == 403


@pytest.mark.parametrize('url', ['/api/train/{id}', '/api/evaluate/{id}', '/api/runs'])
def test_a_visitor_who_is_not_logged_in_gets_401(client, private_run, url):
    assert client.get(url.format(id=private_run.pk)).status_code == 401


def test_a_visitor_who_is_not_logged_in_is_sent_to_login_for_pages(client, private_run):
    for url in (f'/runs/{private_run.pk}/results/', '/datasets/'):
        response = client.get(url)
        assert response.status_code == 302 and '/accounts/login/' in response.url
