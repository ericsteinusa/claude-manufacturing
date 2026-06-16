"""Tests for the Qt-free Customer Service Calls helpers (cs_calls_core).

No DB or PyQt6 (CI can't import Qt) — just the pure label/validation logic.
"""

from manufacturing.cs_calls_core import (
    format_customer_label, parse_customer_id, validate_call)


def test_format_customer_label_with_name():
    assert format_customer_label(7, "Jane", "Doe") == "7 - Jane Doe"


def test_format_customer_label_partial_and_missing_name():
    assert format_customer_label(3, "Jane", "") == "3 - Jane"
    assert format_customer_label(3, "", None) == "3"


def test_parse_customer_id_variants():
    assert parse_customer_id("7 - Jane Doe") == 7
    assert parse_customer_id("7") == 7
    assert parse_customer_id("{7} Jane") == 7
    assert parse_customer_id(7) == 7


def test_parse_customer_id_invalid():
    assert parse_customer_id("") is None
    assert parse_customer_id(None) is None
    assert parse_customer_id("abc") is None


def test_validate_call_ok():
    assert validate_call("7 - Jane Doe", "Printer jammed") == []


def test_validate_call_requires_customer_and_problem():
    errors = validate_call(None, "")
    assert any("customer" in e.lower() for e in errors)
    assert any("description" in e.lower() for e in errors)


def test_validate_call_blank_problem_only():
    assert validate_call(7, "   ") == [
        "Please enter the call / problem description."]
