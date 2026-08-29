"""check_thresholds.py — turns loadtest.yml from "runs and uploads a report"
into an actual pass/fail regression gate.

Reads the "Aggregated" row of the Locust CSV produced by
`run.sh --csv=results` (i.e. `results_stats.csv`) and fails (exit code 1)
if the failure rate or p95 response time exceeds a threshold. Kept as a
standalone script with a pure, testable `evaluate()` function rather than a
shell one-liner (e.g. `awk`/`jq` over the CSV) so the threshold logic has
real unit test coverage — see tests/test_loadtest_check_thresholds.py.

Usage:
    python check_thresholds.py results_stats.csv \
        --max-failure-rate 1.0 --max-p95-ms 3000
"""
import argparse
import csv
import sys


def evaluate(row: dict, max_failure_rate: float, max_p95_ms: float) -> list[str]:
    """Return a list of human-readable violation messages (empty = pass)."""
    violations = []

    request_count = int(row['Request Count'])
    failure_count = int(row['Failure Count'])
    failure_rate = (failure_count / request_count * 100) if request_count > 0 else 0.0
    if failure_rate > max_failure_rate:
        violations.append(
            f"Failure rate {failure_rate:.2f}% exceeds max {max_failure_rate}% "
            f"({failure_count}/{request_count} requests failed)"
        )

    p95 = float(row['95%'])
    if p95 > max_p95_ms:
        violations.append(f"p95 response time {p95:.0f}ms exceeds max {max_p95_ms:.0f}ms")

    return violations


def _load_aggregated_row(csv_path: str) -> dict:
    with open(csv_path, newline='') as f:
        for row in csv.DictReader(f):
            if row['Name'] == 'Aggregated':
                return row
    raise ValueError(f"No 'Aggregated' row found in {csv_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stats_csv', help='Path to Locust\'s results_stats.csv')
    parser.add_argument('--max-failure-rate', type=float, default=1.0,
                         help='Max allowed failure rate, in percent (default: 1.0)')
    parser.add_argument('--max-p95-ms', type=float, default=3000.0,
                         help='Max allowed p95 response time, in ms (default: 3000)')
    args = parser.parse_args()

    row = _load_aggregated_row(args.stats_csv)
    violations = evaluate(row, args.max_failure_rate, args.max_p95_ms)

    if violations:
        print('Load test regression thresholds exceeded:')
        for v in violations:
            print(f'  - {v}')
        return 1

    print(
        f"Load test within thresholds: failure rate "
        f"{int(row['Failure Count'])}/{int(row['Request Count'])} requests, "
        f"p95 {float(row['95%']):.0f}ms (max {args.max_p95_ms:.0f}ms)"
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
