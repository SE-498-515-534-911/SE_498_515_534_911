"""US-39: request, rate and job limits (MLE-SR-006; SAD 4.3.1, 4.4.3; Test Plan SV-06)."""
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from experiments.models import Run
from training import limits

from .conftest import make_frame, store_dataset

pytestmark = pytest.mark.django_db

MB = 1024 * 1024


def error(response):
    return response.json()['error']


# ---- (a) request body over 10 MB -> 413 (SV-06: "send an 11 MB body") -------

def test_11_mb_body_is_refused_with_413(student_client):
    response = student_client.post('/api/train', data=b'x' * (11 * MB), content_type='application/json')
    assert response.status_code == 413
    assert error(response)['code'] == 'PAYLOAD_TOO_LARGE'
    assert error(response)['message'] == 'The request is larger than 10 MB.'


def test_body_just_over_10_mb_is_refused(student_client):
    response = student_client.post('/api/train', data=b'x' * (10 * MB + 1), content_type='application/json')
    assert response.status_code == 413


def test_body_of_exactly_10_mb_is_not_refused_for_its_size(student_client):
    response = student_client.post('/api/train', data=b'x' * (10 * MB), content_type='application/json')
    assert response.status_code != 413


def test_large_body_to_a_page_gets_a_plain_413(client):
    response = client.post('/accounts/login/', data=b'x' * (11 * MB), content_type='text/plain')
    assert response.status_code == 413
    assert response['Content-Type'].startswith('text/plain')


def csv_of_exactly(size):
    head = b'a,b\n'
    row = b'1,' + b'x' * 497 + b'\n'           # 500 bytes per row
    rows, rest = divmod(size - len(head), len(row))
    data = head + row * (rows - 1) + b'1,' + b'x' * (497 + rest) + b'\n'
    assert len(data) == size
    return data


def test_csv_upload_of_exactly_10_mb_is_still_accepted(student_client):
    """SRS Table 4.2-1 accepts a 10 MB file; the form envelope must not push it over (a)."""
    upload = SimpleUploadedFile('ten.csv', csv_of_exactly(10 * MB), content_type='text/csv')
    response = student_client.post('/api/upload', {'file': upload})
    assert response.status_code == 201, response.content[:200]


def test_csv_upload_over_10_mb_gets_the_upload_message(student_client):
    upload = SimpleUploadedFile('big.csv', csv_of_exactly(10 * MB + 1), content_type='text/csv')
    response = student_client.post('/api/upload', {'file': upload})
    assert response.status_code == 413
    assert error(response)['message'] == 'The file is larger than 10 MB.'


def test_file_upload_over_the_request_limit_says_file(student_client):
    """TC-DATA-02: oversize_11MB.csv gets 413 'The file is larger than 10 MB.'"""
    upload = SimpleUploadedFile('oversize.csv', csv_of_exactly(11 * MB), content_type='text/csv')
    response = student_client.post('/api/upload', {'file': upload})
    assert response.status_code == 413
    assert error(response)['code'] == 'PAYLOAD_TOO_LARGE'
    assert error(response)['message'] == 'The file is larger than 10 MB.'


@pytest.mark.parametrize('header', ['', 'abc'])
def test_missing_or_malformed_length_is_left_to_django(rf, header):
    request = rf.post('/api/train', data=b'{}', content_type='application/json')
    request.META['CONTENT_LENGTH'] = header
    assert limits.body_too_large(request) is False


# ---- (b) 120 requests per minute -> 429 (SV-06: "130 requests in one minute") ---

def test_429_after_the_120th_request_from_one_user(student_client):
    codes = [student_client.get('/api/models').status_code for _ in range(130)]
    assert codes[:120] == [200] * 120
    assert codes[120:] == [429] * 10
    response = student_client.get('/api/models')
    assert error(response)['code'] == 'RATE_LIMITED'
    assert error(response)['message'] == 'Too many requests. Please wait and try again.'
    assert 1 <= int(response['Retry-After']) <= 60


def test_limit_is_per_user(client, student, scientist, settings):
    settings.RATE_LIMIT_PER_MINUTE = 3
    client.force_login(student)
    assert [client.get('/api/models').status_code for _ in range(4)] == [200, 200, 200, 429]
    client.force_login(scientist)
    assert client.get('/api/models').status_code == 200


def test_anonymous_requests_are_limited_per_ip_address(client, settings):
    settings.RATE_LIMIT_PER_MINUTE = 2
    first_ip = [client.get('/api/models', REMOTE_ADDR='10.0.0.1').status_code for _ in range(3)]
    assert first_ip == [401, 401, 429]
    assert client.get('/api/models', REMOTE_ADDR='10.0.0.2').status_code == 401


def test_pages_count_too_and_get_a_plain_429(client, settings):
    settings.RATE_LIMIT_PER_MINUTE = 1
    assert client.get('/accounts/login/').status_code == 200
    response = client.get('/accounts/login/')
    assert response.status_code == 429
    assert response.content == b'Too many requests. Please wait and try again.'


def test_static_files_are_not_counted(client, settings):
    settings.RATE_LIMIT_PER_MINUTE = 1
    for _ in range(5):
        client.get('/static/wbmme/app.css')
    assert client.get('/accounts/login/').status_code == 200


def test_window_slides_rather_than_resetting_on_the_minute(settings):
    settings.RATE_LIMIT_PER_MINUTE = 3
    assert [limits.hit('k', now) for now in (100.0, 110.0, 159.0)] == [0, 0, 0]
    assert limits.hit('k', 159.5) == 1          # 3 requests in the last 60 s
    assert limits.hit('k', 160.5) == 0          # the one at 100.0 has left the window
    assert limits.hit('k', 161.0) == 9          # wait until 170.0, when 110.0 leaves


# ---- (c) job quota: Student 1, Data Scientist 2 (SV-06) ------------------------

def train(client, dataset):
    body = {'dataset_id': dataset.pk, 'target_column': 'label', 'model': 'knn'}
    return client.post('/api/train', data=json.dumps(body), content_type='application/json')


def test_second_job_for_a_student_is_refused_with_a_message(student_client, dataset):
    assert train(student_client, dataset).status_code == 202   # stays QUEUED (job waits for commit)
    response = train(student_client, dataset)
    assert response.status_code == 429
    assert error(response)['code'] == 'RATE_LIMITED'
    assert error(response)['message'] == (
        'You already have 1 training job in progress, the limit for a Student. '
        'Wait for one to finish, then try again.')
    assert error(response)['details'] == {'limit': 1}
    assert Run.objects.count() == 1


def test_third_job_for_a_data_scientist_is_refused(client, scientist):
    dataset = store_dataset(scientist, make_frame())
    client.force_login(scientist)
    assert [train(client, dataset).status_code for _ in range(3)] == [202, 202, 429]
    assert 'the limit for a Data Scientist' in error(train(client, dataset))['message']


@pytest.mark.parametrize('finished', [Run.Status.TRAINED, Run.Status.COMPLETED, Run.Status.FAILED])
def test_finished_jobs_free_the_slot(student_client, dataset, finished):
    train(student_client, dataset)
    Run.objects.update(status=finished)
    assert train(student_client, dataset).status_code == 202


def test_quota_is_per_user(client, student, scientist, dataset):
    client.force_login(student)
    train(client, dataset)
    other = store_dataset(scientist, make_frame())
    client.force_login(scientist)
    assert train(client, other).status_code == 202


def test_invalid_request_is_answered_before_the_quota(student_client, dataset):
    train(student_client, dataset)
    body = {'dataset_id': dataset.pk, 'target_column': 'label', 'model': 'svm'}
    response = student_client.post('/api/train', data=json.dumps(body), content_type='application/json')
    assert response.status_code == 400


def test_quota_is_checked_again_when_the_run_is_created(student_client, dataset, monkeypatch):
    """Two requests at the same moment: the second must not slip past the first check."""
    from training import views

    real_split = views.pipeline.load_split

    def another_request_wins(*args, **kwargs):
        Run.objects.create(owner=dataset.owner, dataset=dataset, target_column='label', model_name='knn')
        return real_split(*args, **kwargs)

    monkeypatch.setattr(views.pipeline, 'load_split', another_request_wins)
    assert train(student_client, dataset).status_code == 429
    assert Run.objects.count() == 1


def test_limits_can_be_changed_in_settings(student_client, dataset, settings):
    settings.TRAINING_JOB_LIMITS = {'STUDENT': 2}
    assert [train(student_client, dataset).status_code for _ in range(3)] == [202, 202, 429]


def test_admin_has_no_job_quota_because_admins_cannot_train(admin_user):
    assert limits.job_limit(admin_user) == 0


# ---- (d) time-out is covered by US-21 ------------------------------------------
# training/tests/test_containment.py::test_job_that_never_finishes_is_stopped_at_the_time_limit
