"""Tests for log_utils.get_logger."""

import logging

from manufacturing.log_utils import get_logger


def test_get_logger_returns_named_logger():
    log = get_logger("manufacturing.test.sample")
    assert isinstance(log, logging.Logger)
    assert log.name == "manufacturing.test.sample"


def test_get_logger_defaults_to_root_when_no_name():
    assert get_logger() is logging.getLogger()


def test_configure_is_idempotent():
    # First call configures the root logger; subsequent calls must not
    # keep adding handlers.
    get_logger("a")
    count = len(logging.getLogger().handlers)
    get_logger("b")
    get_logger("c")
    assert len(logging.getLogger().handlers) == count


def test_root_has_a_handler_after_use():
    get_logger("d")
    assert logging.getLogger().handlers
