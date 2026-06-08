"""
log_utils.py — Shared logging helper.

Usage:
    from log_utils import get_logger

    log = get_logger(__name__)
    log.info("AP invoice posted: %s", reference)
    log.error("Failed to post GL entry", exc_info=True)

The first call configures the root handler (stream + optional file). Set the
LOG_LEVEL env var (DEBUG/INFO/WARNING/ERROR) to control verbosity and LOG_FILE
to also write to a file.
"""

import logging
import os

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure():
    global _configured
    if _configured:
        return

    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))

    formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)

    log_file = os.environ.get("LOG_FILE")
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    _configured = True


def get_logger(name=None):
    """
    Return a configured logger.

    Parameters
    ----------
    name : str, optional
        Logger name; pass __name__ from the calling module. Defaults to the
        root logger when omitted.
    """
    _configure()
    return logging.getLogger(name)
