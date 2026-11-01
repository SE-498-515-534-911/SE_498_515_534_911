"""US-30: the load-test tools (loadtest/seed.py and the pass/fail rule of loadtest/locustfile.py).

The 5-minute load test itself needs a running server and is run by hand
(docs/member2/stories/US-30-load-test.md). These tests keep its tools correct.
"""
import io
import sys
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model

from experiments.models import Run

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'loadtest'))
import seed  # noqa: E402  (loadtest/seed.py)

pytestmark = pytest.mark.django_db


def test_seed_creates_accounts_with_completed_runs(client):
    out = io.StringIO()
    created = seed.seed(users=2, runs=4, stdout=out)
    assert list(created) == ['load_user_01', 'load_user_02']
    for name, run_ids in created.items():
        user = get_user_model().objects.get(username=name)
        assert user.role == 'DATA_SCIENTIST'
        runs = Run.objects.filter(owner=user)
        assert sorted(runs.values_list('pk', flat=True)) == sorted(run_ids)
        assert set(runs.values_list('status', flat=True)) == {'COMPLETED'}
        assert set(runs.values_list('model_name', flat=True)) == set(seed.MODELS)
    # The accounts work with the password the locustfile uses.
    assert client.login(username='load_user_01', password=seed.LOAD_TEST_PASSWORD)


def test_seed_can_be_run_again_without_duplicates():
    seed.seed(users=1, runs=1, stdout=io.StringIO())
    out = io.StringIO()
    assert seed.seed(users=1, runs=1, stdout=out) == {}
    assert 'already there, skipped' in out.getvalue()
    assert get_user_model().objects.filter(username__startswith='load_user_').count() == 1


def test_sample_data_passes_the_upload_rules():
    from django.core.files.uploadedfile import SimpleUploadedFile

    from datasets.validators import validate_upload

    info = validate_upload(SimpleUploadedFile('s.csv', seed.sample_csv(), content_type='text/csv'))
    assert (info.rows, info.columns) == (1000, 5)


# ---- the pass/fail rule of MLE-NF-003 ------------------------------------------

class Entry:
    def __init__(self, name, avg, p95, failures=0, count=100):
        self.name, self.avg_response_time, self._p95 = name, avg, p95
        self.num_failures, self.num_requests, self.max_response_time = failures, count, p95

    def get_response_time_percentile(self, percent):
        assert percent == 0.95
        return self._p95


class Stats:
    def __init__(self, *entries):
        self.entries = {e.name: e for e in entries}
        self.total = Entry('total', 0, 0, sum(e.num_failures for e in entries), sum(e.num_requests for e in entries))
        self.total.total_rps = 10.0


@pytest.fixture
def verdict():
    import nf003   # loadtest/nf003.py: no Locust import, so it is safe inside the test run

    return nf003.verdict


def test_passes_when_every_page_is_within_3_seconds(verdict):
    passed, lines = verdict(Stats(Entry('dashboard', 40, 120), Entry('results page', 2999, 3000)))
    assert passed and lines[-1].endswith('PASS')


@pytest.mark.parametrize('entry', [
    Entry('dashboard', 3001, 3001),          # average too slow
    Entry('dashboard', 500, 3100),           # 95th percentile too slow
    Entry('dashboard', 40, 120, failures=1), # a failed request (for example a 500)
])
def test_fails_on_a_slow_page_or_any_failure(verdict, entry):
    passed, lines = verdict(Stats(Entry('results page', 30, 90), entry))
    assert not passed and lines[-1].endswith('FAIL')


def test_fails_when_nothing_was_measured(verdict):
    assert verdict(Stats())[0] is False
