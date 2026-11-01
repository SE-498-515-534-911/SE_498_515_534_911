"""TC-PERF-03 load test (US-30, MLE-NF-003) with Locust.

MLE-NF-003: with 20 concurrent logged-in users, every application page shall
load in 3 seconds or less, for both the average and the 95th percentile, over
a run of 5 minutes, and the run shall produce no server errors (HTTP 5xx).

TC-PERF-03: 20 users, each with an account and sample runs (loadtest/seed.py),
log in and open the dashboard, history and results repeatedly for 5 minutes.

    python loadtest/seed.py                                  # once, against the server's database
    locust -f loadtest/locustfile.py --host http://127.0.0.1:8000 \\
           --headless --users 20 --spawn-rate 5 --run-time 5m --csv loadtest/results/tc_perf_03

The test passes (exit code 0) when every page meets the limits and no request
failed. Each simulated user has its own account, as real users do, so the
per-user rate limit of MLE-SR-006 applies to each separately.
"""
import itertools
import threading

from locust import HttpUser, between, events, task

from nf003 import verdict

PASSWORD = 'LoadTest!2026pw'      # same as loadtest/seed.py
_numbers = itertools.count(1)
_numbers_lock = threading.Lock()


def next_username():
    with _numbers_lock:
        number = next(_numbers)
    return f'load_user_{(number - 1) % 20 + 1:02d}'


class WbmmeUser(HttpUser):
    wait_time = between(1, 3)     # time a person spends reading a page

    def on_start(self):
        self.username = next_username()
        self.run_ids, self.results_opened = [], 0
        # Log in through the login page, as a browser does.
        self.client.get('/accounts/login/', name='login page')
        token = self.client.cookies.get('csrftoken', '')
        with self.client.post('/accounts/login/', name='log in', allow_redirects=False, catch_response=True,
                              data={'username': self.username, 'password': PASSWORD,
                                    'csrfmiddlewaretoken': token},
                              headers={'Referer': self.host + '/accounts/login/'}) as response:
            if response.status_code != 302:
                response.failure(f'login failed for {self.username}: HTTP {response.status_code}')
                return
        history = self.client.get('/api/runs', name='history (/api/runs)').json()
        self.run_ids = [run['run_id'] for run in history.get('runs', [])]
        self.results_opened = 0

    @task(3)
    def dashboard(self):
        self.client.get('/', name='dashboard')

    @task(3)
    def history(self):
        self.client.get('/api/runs', name='history (/api/runs)')

    @task(3)
    def results(self):
        if not self.run_ids:
            return
        run_id = self.run_ids[self.results_opened % len(self.run_ids)]   # each run in turn
        self.results_opened += 1
        self.client.get(f'/runs/{run_id}/results/', name='results page')
        # The results page's script asks for the numbers right away; the page is
        # usable once this answers, so it is measured as part of opening results.
        self.client.get(f'/api/evaluate/{run_id}', name='results data (/api/evaluate)')

    @task(2)
    def datasets(self):
        self.client.get('/datasets/', name='datasets page')

    @task(1)
    def home(self):
        self.client.get('/accounts/', name='account home')


@events.quitting.add_listener
def _report(environment, **kwargs):
    passed, lines = verdict(environment.stats)
    print('\n'.join(lines))
    environment.process_exit_code = 0 if passed else 1
