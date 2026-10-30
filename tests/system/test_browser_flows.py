"""US-28 system tests in a real browser (Test Plan section 5: "end-to-end flows through the browser").

The steps of Appendix A that depend on what the pages draw with JavaScript:
TC-AUTH-01 steps 1-2 and TC-DATA-01 through the login and upload pages, and
TC-EVAL-01 steps 1-3 (the results page renders the metrics and the confusion
matrix). Uses Playwright with Chromium. It is not in requirements.txt, so these
tests are skipped where it is not installed (for example in CI); to run them:

    pip install playwright pytest-playwright && python -m playwright install chromium
    python -m pytest tests/system/test_browser_flows.py
"""
import os

import pytest

from support.data import csv_bytes, iris_like, sample_1000rows

from .conftest import PASSWORD

sync_api = pytest.importorskip('playwright.sync_api', exc_type=ImportError)
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def page(live_server, monkeypatch):
    # Playwright's sync API runs an event loop in this thread; the test still uses the ORM.
    monkeypatch.setenv('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')
    with sync_api.sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - no browser installed on this machine
            pytest.skip(f'Chromium is not available: {exc}')
        page = chromium.new_page(base_url=live_server.url)
        # Problems that count: JavaScript errors, and WBMME's own requests failing.
        # (External resources such as web fonts may be unreachable where the tests run.)
        page.console_errors = []
        page.on('pageerror', lambda exc: page.console_errors.append(str(exc)))
        page.on('console', lambda msg: msg.type == 'error' and not msg.text.startswith('Failed to load resource')
                and page.console_errors.append(msg.text))
        page.on('response', lambda r: r.url.startswith(live_server.url) and r.status >= 500
                and page.console_errors.append(f'{r.status} {r.url}'))
        page.on('requestfailed', lambda r: r.url.startswith(live_server.url)
                and page.console_errors.append(f'failed {r.url}'))
        yield page
        chromium.close()


def log_in(page, username):
    page.goto('/accounts/login/')
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state()


def test_login_page_and_upload_page_in_the_browser(accounts, page, tmp_path):
    """TC-AUTH-01 steps 1-2 and TC-DATA-01 steps 1-3 through the real pages."""
    log_in(page, 'ds_test1')
    assert '/accounts/login' not in page.url                     # logged in

    page.goto('/datasets/')
    sample = tmp_path / 'sample_1000rows.csv'
    sample.write_bytes(csv_bytes(sample_1000rows()))
    page.set_input_files('#dataset-file', str(sample))
    page.click('#upload-form button[type="submit"]')
    status = page.locator('#upload-status')
    sync_api.expect(status).to_contain_text('Uploaded sample_1000rows.csv — 1000 rows and 5 columns')
    page.wait_for_load_state()
    sync_api.expect(page.locator('#saved-list')).to_contain_text('sample_1000rows.csv', timeout=10_000)
    assert page.console_errors == []


def test_wrong_password_shows_an_error_on_the_login_page(accounts, page):
    """TC-AUTH-01 step 4 in the browser: refused, still on the login page."""
    page.goto('/accounts/login/')
    page.fill('input[name="username"]', 'ds_test1')
    page.fill('input[name="password"]', 'Wrong#123')
    page.click('button[type="submit"]')
    page.wait_for_load_state()
    assert '/accounts/login' in page.url
    sync_api.expect(page.locator('.form-errors')).to_be_visible()


def test_results_page_draws_metrics_and_confusion_matrix(accounts, page, tmp_path):
    """TC-EVAL-01 steps 1-3: open the results page; tiles, chart and matrix render."""
    log_in(page, 'ds_test1')
    page.goto('/datasets/')
    iris = tmp_path / 'iris_like.csv'
    iris.write_bytes(csv_bytes(iris_like()))
    page.set_input_files('#dataset-file', str(iris))
    page.click('#upload-form button[type="submit"]')
    sync_api.expect(page.locator('#upload-status')).to_contain_text('Uploaded iris_like.csv')
    sync_api.expect(page.locator('[data-dataset-id]')).to_have_count(1, timeout=10_000)   # after the reload

    # Start training the way a page script would (there is no Train screen yet).
    run = page.evaluate("""async () => {
        const csrf = document.querySelector('meta[name="csrf-token"]').content;
        const upload = document.querySelector('[data-dataset-id]');
        const response = await fetch('/api/train', {method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
            body: JSON.stringify({dataset_id: Number(upload.dataset.datasetId), target_column: 'species',
                                  model: 'logistic_regression', split: {test_size: 0.2, random_state: 42}})});
        return {status: response.status, body: await response.json()};
    }""")
    assert run['status'] == 202, run

    page.goto(f"/runs/{run['body']['run_id']}/results/")
    sync_api.expect(page.locator('#run-status')).to_have_text('Completed', timeout=60_000)
    assert page.locator('#metric-tiles .metric-tile').count() >= 4
    sync_api.expect(page.locator('#matrix-total')).to_have_text('24')       # 20% of 120 rows
    assert page.locator('#confusion-matrix td').count() >= 9               # 3 x 3 classes
    assert page.locator('#chart-missing').is_hidden()                      # Chart.js drew the chart
    assert page.console_errors == []
