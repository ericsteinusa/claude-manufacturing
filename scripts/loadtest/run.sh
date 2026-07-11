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
locust -f locustfile.py --host "$HOST" \
  --headless -u "$USERS" -r "$SPAWN_RATE" -t "$DURATION" \
  --csv=results --html=report.html

echo
echo "Results: scripts/loadtest/results_stats.csv, scripts/loadtest/report.html"
