"""Tests for scripts/loadtest/check_thresholds.py — Qt-free, no live DB.

scripts/loadtest/ isn't part of the manufacturing/ package (it's a
standalone CI/dev tool, not imported by views/seeds/other core modules),
so it's added to sys.path directly rather than via a package import.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts' / 'loadtest'))

from check_thresholds import evaluate  # noqa: E402


def _row(request_count=100, failure_count=0, p95='500'):
    return {'Request Count': str(request_count), 'Failure Count': str(failure_count), '95%': p95}


def test_evaluate_passes_within_thresholds():
    violations = evaluate(_row(request_count=100, failure_count=0, p95='500'),
                           max_failure_rate=1.0, max_p95_ms=3000.0)
    assert violations == []


def test_evaluate_flags_high_failure_rate():
    violations = evaluate(_row(request_count=100, failure_count=5, p95='500'),
                           max_failure_rate=1.0, max_p95_ms=3000.0)
    assert len(violations) == 1
    assert '5.00%' in violations[0]
    assert 'Failure rate' in violations[0]


def test_evaluate_flags_high_p95():
    violations = evaluate(_row(request_count=100, failure_count=0, p95='4500'),
                           max_failure_rate=1.0, max_p95_ms=3000.0)
    assert len(violations) == 1
    assert 'p95 response time 4500ms' in violations[0]


def test_evaluate_flags_both_thresholds_at_once():
    violations = evaluate(_row(request_count=100, failure_count=10, p95='9000'),
                           max_failure_rate=1.0, max_p95_ms=3000.0)
    assert len(violations) == 2


def test_evaluate_zero_requests_does_not_divide_by_zero():
    violations = evaluate(_row(request_count=0, failure_count=0, p95='0'),
                           max_failure_rate=1.0, max_p95_ms=3000.0)
    assert violations == []


def test_evaluate_exact_threshold_is_not_a_violation():
    violations = evaluate(_row(request_count=100, failure_count=1, p95='3000'),
                           max_failure_rate=1.0, max_p95_ms=3000.0)
    assert violations == []
