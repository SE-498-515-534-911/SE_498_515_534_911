"""US-20 / MLE-NF-002: dense features and the TC-PERF-02 benchmark script.

The full 50,000-row benchmark takes minutes and needs a running server, so it
is run by hand (see docs/member2/stories/US-20-training-speed.md). These tests
are fast and keep the pieces it depends on correct.
"""
import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from training import pipeline
from training.benchmarks import tc_perf_02

from .conftest import make_frame


# ---- dense features (the fix) --------------------------------------------------

def test_prepared_width_counts_one_hot_columns_with_the_cap():
    X = pd.DataFrame({
        'n1': [1.0, 2.0, 3.0],
        'n2': [1, 2, 3],
        'few': ['a', 'b', 'a'],
        'many': [f'c{i}' for i in range(3)],
    })
    assert pipeline.prepared_width(X) == 2 + (2 + 1) + (3 + 1)
    wide = pd.DataFrame({'id': [f'x{i}' for i in range(100)]})
    assert pipeline.prepared_width(wide) == pipeline.MAX_ONE_HOT_CATEGORIES


def test_normal_data_is_prepared_as_a_dense_array():
    split = pipeline.make_split(make_frame(), 'label', 'median', 0.2, 42)
    pipe = pipeline.build_pipeline('random_forest', {'n_estimators': 10}, 42, split.X_train)
    pipe.fit(split.X_train, split.y_train)
    prepared = pipe.named_steps['prepare'].transform(split.X_test)
    assert isinstance(prepared, np.ndarray)


def test_very_large_tables_stay_sparse_to_protect_memory(monkeypatch):
    split = pipeline.make_split(make_frame(), 'label', 'median', 0.2, 42)
    monkeypatch.setattr(pipeline, 'MAX_DENSE_CELLS', 10)
    assert not pipeline.use_dense(split.X_train)
    pipe = pipeline.build_pipeline('decision_tree', {}, 42, split.X_train)
    pipe.fit(split.X_train, split.y_train)
    assert sparse.issparse(pipe.named_steps['prepare'].transform(split.X_test))


def test_the_benchmark_size_is_far_below_the_dense_limit():
    X = tc_perf_02.make_dataset().drop(columns='target')
    assert int(len(X) * 0.8) * pipeline.prepared_width(X) < pipeline.MAX_DENSE_CELLS / 10


# ---- TC-PERF-02 test data --------------------------------------------------------

def test_dataset_has_the_shape_tc_perf_02_asks_for():
    df = tc_perf_02.make_dataset()
    assert df.shape == (50_000, 21)                     # 20 feature columns + target
    assert df['target'].nunique() == 3
    assert df.isna().any().any()                         # some missing values to fill
    assert len(df.select_dtypes(include='number').columns) == 15   # + 5 text features


def test_dataset_fits_the_10_mb_upload_limit_and_is_reproducible():
    first = tc_perf_02.csv_bytes(tc_perf_02.make_dataset())
    assert len(first) < 10 * 1024 * 1024
    assert first == tc_perf_02.csv_bytes(tc_perf_02.make_dataset())


def test_write_csv_option(tmp_path):
    target = tmp_path / 'generated.csv'
    assert tc_perf_02.main(['--write-csv', str(target), '--rows', '50']) == 0
    assert pd.read_csv(target).shape == (50, 21)


# ---- pass/fail rules -----------------------------------------------------------

def watcher_with(times, failures=0):
    watcher = tc_perf_02.DashboardWatcher(client=None)
    watcher.times, watcher.failures = times, failures
    return watcher.summary()


def test_dashboard_passes_when_every_load_is_fast():
    summary = watcher_with([0.1, 0.2, 2.9])
    assert summary['passed'] and summary['max_seconds'] == 2.9


@pytest.mark.parametrize('times, failures', [([0.1, 3.5], 0), ([0.1, 0.1], 1)])
def test_dashboard_fails_on_a_slow_load_or_an_error(times, failures):
    assert not watcher_with(times, failures)['passed']


# ---- the script end to end, on a small dataset ----------------------------------

@pytest.mark.django_db(transaction=True)
def test_script_runs_tc_perf_02_end_to_end_against_a_server(live_server, settings, capsys):
    settings.TRAINING_JOBS_INLINE = False   # a real background thread, as in production
    report = tc_perf_02.run(live_server.url, rows=400, models=('logistic_regression', 'decision_tree'))
    assert [r['status'] for r in report['results']] == ['COMPLETED', 'COMPLETED']
    assert all(r['seconds_to_completed'] <= tc_perf_02.LIMIT_SECONDS for r in report['results'])
    assert report['dataset']['feature_columns'] == 20
    assert report['dashboard']['failures'] == 0
    assert report['passed']
    tc_perf_02.print_report(report)
    assert 'OVERALL: PASS' in capsys.readouterr().out


@pytest.mark.django_db(transaction=True)
def test_script_reports_a_refused_job_as_a_failure(live_server):
    client = tc_perf_02.Client(live_server.url)
    client.sign_in('perf_refused', 'DATA_SCIENTIST')
    result = tc_perf_02.time_one_model(client, dataset_id=999, model='knn')
    assert result == {'model': 'knn', 'status': 'HTTP 404',
                      'error': result['error'], 'passed': False}
    assert result['error']['code'] == 'NOT_FOUND'


def test_no_answer_counts_as_a_failure_instead_of_crashing():
    client = tc_perf_02.Client('http://127.0.0.1:9', timeout=1)   # nothing listens on port 9
    status, body = client.json('GET', '/api/models')
    assert status == 0 and body['error']['code'] == 'NO_RESPONSE'
