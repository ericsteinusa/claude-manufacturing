"""Tests for launch_utils.launch (the shared department-menu launcher).

subprocess.Popen is monkeypatched so no real processes are spawned.
"""

import sys

import pytest

from manufacturing import launch_utils


@pytest.fixture
def captured_popen(monkeypatch):
    """Replace subprocess.Popen with a recorder; return the capture dict."""
    captured = {}

    def fake_popen(cmd, cwd=None, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return object()

    monkeypatch.setattr(launch_utils.subprocess, "Popen", fake_popen)
    return captured


def test_launch_builds_module_command(captured_popen):
    launch_utils.launch("IT_mgr.py")
    assert captured_popen["cmd"][:2] == [sys.executable, "-m"]
    assert captured_popen["cmd"][2] == "manufacturing.IT_mgr"


def test_launch_strips_extension(captured_popen):
    launch_utils.launch("IT_mgr.py")
    with_ext = captured_popen["cmd"][2]
    launch_utils.launch("IT_mgr")
    without_ext = captured_popen["cmd"][2]
    assert with_ext == without_ext == "manufacturing.IT_mgr"


def test_launch_runs_from_repo_root(captured_popen):
    launch_utils.launch("anything.py")
    # _CWD is the parent of the manufacturing package directory.
    assert captured_popen["cwd"] == launch_utils._CWD


def test_launch_reraises_on_popen_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("cannot spawn")

    monkeypatch.setattr(launch_utils.subprocess, "Popen", boom)
    with pytest.raises(OSError):
        launch_utils.launch("IT_mgr.py")
