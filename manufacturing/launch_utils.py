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
        import tempfile, threading, time
        err_path = os.path.join(
            tempfile.gettempdir(),
            f'mfg_{os.path.splitext(script)[0]}.log',
        )
        with open(err_path, 'w') as err_file:
            p = subprocess.Popen(
                [sys.executable, "-m", module, *args],
                cwd=_CWD,
                stderr=err_file,
                stdout=err_file,
            )

        def _watch(proc, path, mod_name):
            time.sleep(4)           # give window time to appear
            if proc.poll() is None:
                return              # still running — all good
            rc = proc.returncode
            if rc in (0, -15, 15, -2):  # normal exits
                return
            try:
                with open(path) as f:
                    msg = f.read(4000).strip()
            except OSError:
                msg = "(no output captured)"
            log.error("Module %s crashed (rc=%s):\n%s", mod_name, rc, msg)
            print(f"\n[ERROR] {mod_name} crashed (rc={rc}):\n{msg}\n",
                  flush=True)

        threading.Thread(target=_watch, args=(p, err_path, module),
                         daemon=True).start()
    except Exception:
        log.error("Failed to launch %s", module, exc_info=True)
        raise
