"""locustfile.py — Load testing for Manufacture ERP (Phase 3).

Simulates realistic logged-in browsing across several departments' list
pages. What to watch for isn't a specific pass/fail threshold, but whether
response times and error rates climb disproportionately as concurrency
increases -- the thing this is specifically checking is whether
manufacturing/db_pg.py's get_db_connection() (a fresh Postgres connection
per call, flagged as a concern since Phase 1's DEPLOYMENT.md) actually
bottlenecks under real concurrent traffic.

Usage: see scripts/loadtest/run.sh, or directly:

    locust -f scripts/loadtest/locustfile.py --host http://localhost:8080

Credentials default to the sample seed data (manufacturing/seeds/
seed_sample_data.py) -- override via LOADTEST_EMAIL / LOADTEST_PASSWORD to
point this at a real deployment's own data instead.
"""

import os
import re

from locust import HttpUser, between, task

EMAIL = os.environ.get('LOADTEST_EMAIL', 'james.carter@example.com')
PASSWORD = os.environ.get('LOADTEST_PASSWORD', 'Sample123!')

_CSRF_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')


class ManufactureUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        login_page = self.client.get('/', name='/ (login page)')
        match = _CSRF_RE.search(login_page.text)
        if not match:
            raise RuntimeError('Could not find CSRF token on the login page.')

        with self.client.post(
            '/',
            {
                'csrfmiddlewaretoken': match.group(1),
                'email': EMAIL,
                'password': PASSWORD,
            },
            name='/ (login submit)',
            catch_response=True,
        ) as resp:
            # A failed login re-renders the same form (200), it doesn't 4xx/5xx
            # -- checking the final URL after redirects is the real signal,
            # same distinction manufacturing.accounts._verify_login's caller
            # relies on (redirect to /dashboard/ vs. re-rendering /).
            if '/dashboard/' not in resp.url:
                resp.failure(f'Login did not reach /dashboard/ (landed on {resp.url})')

    @task(3)
    def dashboard(self):
        self.client.get('/dashboard/')

    @task(2)
    def work_orders(self):
        self.client.get('/wo/')

    @task(2)
    def inventory(self):
        self.client.get('/inventory/')

    @task(2)
    def purchase_orders(self):
        self.client.get('/po/')

    @task(1)
    def sales_orders(self):
        self.client.get('/so/')

    @task(1)
    def quality(self):
        self.client.get('/qa/')
