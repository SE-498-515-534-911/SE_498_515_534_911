"""TC-PERF-02: training speed (US-20, MLE-NF-002), run against a live WBMME server.

MLE-NF-002: training any catalogue model with its default parameters on a
dataset of up to 50,000 rows and 20 feature columns shall complete in 60
seconds or less, and the dashboard shall stay responsive while the job runs.

The script follows TC-PERF-02 step by step:
  0. generate the test data set (generated_50k_rows_20_features.csv) and upload it;
  1. train each of the four catalogue models with default settings;
  2. record the time from start to Completed (training, then evaluation);
  3. while training, a second user loads the dashboard every second.

Pass: every model reaches COMPLETED within 60 s, and every dashboard load
returns 200 within 3 s (the page-load limit of MLE-NF-003).

Usage (server running, for example `docker compose up` or `python manage.py runserver`):
    python training/benchmarks/tc_perf_02.py --url http://127.0.0.1:8000
    python training/benchmarks/tc_perf_02.py --write-csv generated_50k_rows_20_features.csv

Only the Python standard library plus numpy and pandas is used; the exit code
is 0 when every check passes and 1 otherwise.
"""
import argparse
import http.cookiejar
import json
import os
import platform
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

LIMIT_SECONDS = 60.0
DASHBOARD_LIMIT_SECONDS = 3.0
ROWS = 50_000
NUMERIC = 15
TEXT = 5
MODELS = ('logistic_regression', 'knn', 'decision_tree', 'random_forest')
PASSWORD = 'Perf!Test2026pw'


# ---- test data ---------------------------------------------------------------

def make_dataset(rows=ROWS, seed=0):
    """20 feature columns (15 numeric, 3 of them with 5% missing; 5 text with 8 values) and a 3-class target.

    Numbers have 3 decimals, as real measurements do, which keeps the 50,000-row
    file under the 10 MB upload limit. The same seed always gives the same file.
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    data = {f'num_{i}': rng.normal(size=rows).round(3) for i in range(NUMERIC)}
    for i in range(TEXT):
        data[f'cat_{i}'] = rng.choice([f'v{j}' for j in range(8)], rows)
    df = pd.DataFrame(data)
    score = df['num_0'] + 0.5 * df['num_1'] - 0.5 * df['num_2'] + (df['cat_0'] == 'v1') \
        + rng.normal(scale=0.5, size=rows)
    df['target'] = np.digitize(score, np.quantile(score, [1 / 3, 2 / 3])).astype(str)
    for column in ('num_3', 'num_4', 'num_5'):
        df.loc[rng.random(rows) < 0.05, column] = np.nan
    return df


def csv_bytes(df):
    return df.to_csv(index=False).encode('utf-8')


# ---- a tiny HTTP client (standard library only) ------------------------------

class Client:
    def __init__(self, base, timeout=180):
        self.base = base.rstrip('/')
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _csrf(self):
        return next((c.value for c in self.jar if c.name == 'csrftoken'), '')

    def request(self, method, path, body=None, content_type='application/json'):
        data = json.dumps(body).encode() if isinstance(body, dict) else body
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header('Referer', self.base + '/')
        if data is not None:
            req.add_header('Content-Type', content_type)
        if method != 'GET':
            req.add_header('X-CSRFToken', self._csrf())
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except (TimeoutError, urllib.error.URLError) as exc:
            return 0, json.dumps({'error': {'code': 'NO_RESPONSE', 'message': str(exc)}}).encode()

    def json(self, method, path, body=None):
        status, raw = self.request(method, path, body)
        try:
            return status, json.loads(raw or b'{}')
        except ValueError:
            return status, {}

    def sign_in(self, username, role):
        self.request('GET', '/accounts/login/')  # sets the CSRF cookie
        self.json('POST', '/api/auth/register', {
            'username': username, 'password': PASSWORD, 'role': role, 'email': f'{username}@example.com'})
        status, _ = self.json('POST', '/api/auth/login', {'username': username, 'password': PASSWORD})
        if status != 200:
            raise SystemExit(f'Could not log in as {username} (HTTP {status}).')

    def upload(self, name, content):
        boundary = uuid.uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            'Content-Type: text/csv\r\n\r\n'
        ).encode() + content + f'\r\n--{boundary}--\r\n'.encode()
        status, raw = self.request('POST', '/api/upload', body, f'multipart/form-data; boundary={boundary}')
        if status != 201:
            raise SystemExit(f'Upload failed (HTTP {status}): {raw[:300]!r}')
        return json.loads(raw)['dataset']['id']


# ---- the measurement ---------------------------------------------------------

def time_one_model(client, dataset_id, model, poll=1.0):
    """Start a default training run and wait for COMPLETED. Returns a result dict."""
    start = time.perf_counter()
    status, body = client.json('POST', '/api/train', {
        'dataset_id': dataset_id, 'target_column': 'target', 'model': model})
    if status != 202:
        return {'model': model, 'status': f'HTTP {status}', 'error': body.get('error'), 'passed': False}
    run_id = body['run_id']
    trained_at = None
    while time.perf_counter() - start < LIMIT_SECONDS * 3:
        _, run = client.json('GET', f'/api/train/{run_id}')
        if run.get('status') in ('TRAINED', 'COMPLETED', 'FAILED'):
            trained_at = time.perf_counter()
            break
        time.sleep(poll)
    _, evaluation = client.json('GET', f'/api/evaluate/{run_id}')  # evaluation runs on this request
    done = time.perf_counter()
    seconds = round(done - start, 2)
    final = evaluation.get('status', run.get('status'))
    return {
        'model': model,
        'run_id': run_id,
        'status': final,
        'seconds_to_trained': round(trained_at - start, 2) if trained_at else None,
        'seconds_to_completed': seconds,
        'test_accuracy': (evaluation.get('metrics') or {}).get('test', {}).get('accuracy'),
        'error': evaluation.get('error') or run.get('error'),
        'passed': final == 'COMPLETED' and seconds <= LIMIT_SECONDS,
    }


class DashboardWatcher(threading.Thread):
    """TC-PERF-02 step 3: another user loads the dashboard every second while jobs run."""

    def __init__(self, client):
        super().__init__(daemon=True)
        self.client, self.times, self.failures = client, [], 0
        self.stopping = threading.Event()

    def run(self):
        while not self.stopping.is_set():
            started = time.perf_counter()
            status, _ = self.client.request('GET', '/')
            self.times.append(time.perf_counter() - started)
            self.failures += status != 200
            self.stopping.wait(1.0)

    def summary(self):
        times = sorted(self.times) or [0.0]
        return {
            'loads': len(self.times),
            'failures': self.failures,
            'average_seconds': round(statistics.mean(times), 3),
            'p95_seconds': round(times[max(0, int(len(times) * 0.95) - 1)], 3),
            'max_seconds': round(times[-1], 3),
            'passed': self.failures == 0 and times[-1] <= DASHBOARD_LIMIT_SECONDS,
        }


def run(url, rows=ROWS, models=MODELS):
    suffix = uuid.uuid4().hex[:6]
    trainer, watcher_client = Client(url), Client(url)
    trainer.sign_in(f'perf_ds_{suffix}', 'DATA_SCIENTIST')
    watcher_client.sign_in(f'perf_watch_{suffix}', 'DATA_SCIENTIST')

    content = csv_bytes(make_dataset(rows))
    upload_started = time.perf_counter()
    dataset_id = trainer.upload('generated_50k_rows_20_features.csv', content)
    upload_seconds = round(time.perf_counter() - upload_started, 2)

    watcher = DashboardWatcher(watcher_client)
    watcher.start()
    results = [time_one_model(trainer, dataset_id, model) for model in models]
    watcher.stopping.set()
    watcher.join(5)

    dashboard = watcher.summary()
    return {
        'test_case': 'TC-PERF-02',
        'requirement': 'MLE-NF-002',
        'url': url,
        'dataset': {'rows': rows, 'feature_columns': NUMERIC + TEXT, 'bytes': len(content),
                    'upload_seconds': upload_seconds},
        'client_machine': {'platform': platform.platform(), 'python': platform.python_version(),
                           'cpus': os.cpu_count()},
        'limit_seconds': LIMIT_SECONDS,
        'results': results,
        'dashboard': dashboard,
        'passed': all(r['passed'] for r in results) and dashboard['passed'],
    }


def print_report(report):
    print(f"TC-PERF-02 against {report['url']}: {report['dataset']['rows']:,} rows, "
          f"{report['dataset']['feature_columns']} features, {report['dataset']['bytes'] / 2**20:.2f} MB")
    print(f"{'Model':<22}{'To TRAINED':>12}{'To COMPLETED':>14}{'Accuracy':>10}  Result")
    for r in report['results']:
        accuracy = f"{r['test_accuracy']:.3f}" if r.get('test_accuracy') is not None else '-'
        print(f"{r['model']:<22}{r.get('seconds_to_trained') or '-':>11}s"
              f"{r.get('seconds_to_completed') or '-':>13}s{accuracy:>10}  "
              f"{'PASS' if r['passed'] else 'FAIL ' + str(r.get('error') or r['status'])}")
    d = report['dashboard']
    print(f"Dashboard while training: {d['loads']} loads, {d['failures']} failures, "
          f"average {d['average_seconds']} s, max {d['max_seconds']} s  {'PASS' if d['passed'] else 'FAIL'}")
    print('OVERALL:', 'PASS' if report['passed'] else 'FAIL')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--rows', type=int, default=ROWS)
    parser.add_argument('--json', help='also write the report to this file')
    parser.add_argument('--write-csv', help='only write the test data set to this file and stop')
    args = parser.parse_args(argv)

    if args.write_csv:
        with open(args.write_csv, 'wb') as handle:
            handle.write(csv_bytes(make_dataset(args.rows)))
        print(f'Wrote {args.write_csv}')
        return 0

    report = run(args.url, args.rows)
    print_report(report)
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
