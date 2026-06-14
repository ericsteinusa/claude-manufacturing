"""
launch_utils.py — Shared helper for launching department menu modules.

Usage:
    from launch_utils import launch

    launch("IT_mgr.py")          # runs `python -m manufacturing.IT_mgr`

Each department menu used to define its own identical ``_launch`` helper;
this centralizes that boilerplate (and its logging) in one place.
"""

import os
import sys
import subprocess

from .log_utils import get_logger

log = get_logger(__name__)

# Repo root — the parent of the manufacturing package directory. Modules are
# launched with this as the working directory, matching the original per-file
# helpers (which computed the same path from their own __file__).
_CWD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def launch(script, *args):
    """Launch a sibling manufacturing module in a new process.

    Parameters
    ----------
    script : str
        A module name or filename (e.g. "IT_mgr" or "IT_mgr.py"); any
        extension is stripped before building the ``manufacturing.<name>``
        module path.
    *args : str
        Extra positional arguments forwarded to the module's ``sys.argv``
        (e.g. a host department name for a screen that scopes to it).
    """
    module = "manufacturing." + os.path.splitext(script)[0]
    log.info("Launching module %s args=%s", module, args)
    try:
        subprocess.Popen([sys.executable, "-m", module, *args], cwd=_CWD)
    except Exception:
        log.error("Failed to launch %s", module, exc_info=True)
        raise
