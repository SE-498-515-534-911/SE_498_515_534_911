"""The pass/fail rule of MLE-NF-003 for the TC-PERF-03 load test (US-30).

Kept apart from locustfile.py, which imports Locust (and Locust patches
Python's threading as it loads), so the rule can be unit-tested on its own.
"""

LIMIT_MS = 3000


def verdict(stats):
    """Check every request type against MLE-NF-003. Returns (passed, lines of the report)."""
    lines, passed = [], True
    lines.append(f"{'Page / request':<34}{'Count':>7}{'Avg ms':>9}{'p95 ms':>9}{'Max ms':>9}{'Fail':>6}  Result")
    for entry in sorted(stats.entries.values(), key=lambda e: e.name):
        p95 = entry.get_response_time_percentile(0.95) or 0
        ok = entry.num_failures == 0 and entry.avg_response_time <= LIMIT_MS and p95 <= LIMIT_MS
        passed &= ok
        lines.append(f'{entry.name:<34}{entry.num_requests:>7}{entry.avg_response_time:>9.0f}{p95:>9.0f}'
                     f'{entry.max_response_time:>9.0f}{entry.num_failures:>6}  {"PASS" if ok else "FAIL"}')
    total = stats.total
    if total.num_requests == 0:
        passed = False
    lines.append(f'Total: {total.num_requests} requests, {total.num_failures} failures, '
                 f'{total.total_rps:.1f} requests/s')
    lines.append(f'TC-PERF-03 / MLE-NF-003: {"PASS" if passed else "FAIL"}')
    return passed, lines
