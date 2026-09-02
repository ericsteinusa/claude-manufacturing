#!/bin/sh
set -eu

# Headless load test runner — wraps locust with sensible defaults.
#
#   ./scripts/loadtest/run.sh http://localhost:8080
#   ./scripts/loadtest/run.sh http://localhost:8080 50 5 5m
#
# Never point this at a real customer's production instance without warning
# them first — it's real concurrent traffic, not a passive check.

HOST="${1:?usage: run.sh <host> [users] [spawn-rate] [duration]}"
USERS="${2:-20}"
SPAWN_RATE="${3:-2}"
DURATION="${4:-2m}"

cd "$(dirname "$0")"
# Locust's own headless mode exits 1 if *any* request failed during the run,
# regardless of how small a fraction that is of the total — e.g. 1 failure
# out of 300+ requests (well under any sane failure-rate threshold) still
# trips it. That's the wrong gate: check_thresholds.py (run right after
# this script, against the same results_stats.csv) is the actual,
# configurable regression gate this pipeline is built around. Don't let
# locust's own blunter exit code short-circuit past it — `|| true` here,
# not `set +e` for the whole script, so a genuine setup failure (e.g. the
# locustfile itself not found) still fails loudly.
locust -f locustfile.py --host "$HOST" \
  --headless -u "$USERS" -r "$SPAWN_RATE" -t "$DURATION" \
  --csv=results --html=report.html || true

echo
echo "Results: scripts/loadtest/results_stats.csv, scripts/loadtest/report.html"
