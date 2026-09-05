"""Deploy identity for the health endpoint: which commit is this process serving?

Motivated by a real incident (2026-09-04): `manufacture.service` was dead for
eight hours while a leftover dev server held its port, so the box answered
every request normally and nothing outside the machine could tell that the
deployed code was not what was running. Neither could a `git log` on the box
-- the repo had pulled fine; only the *restart* had failed.

That is the distinction this module exists to expose:

  * ``sha``      -- read once at import, so it is the commit this PROCESS
                    started with. This is what the server is actually serving.
  * ``disk_sha`` -- read per request, so it is what the working tree holds now.

They differ exactly in the "pulled but not restarted" window, which is the
failure mode that is otherwise invisible from outside. ``code_stale`` says so
in one boolean.

Reads ``.git`` directly rather than shelling out to ``git``: no subprocess per
request, no dependency on git being installed or on the deploy user's PATH,
and it cannot hang. Every failure path degrades to ``None`` -- a health probe
must never 500 because version metadata was unreadable.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

# Import time == process start. Deliberately module-level: it is what makes
# `sha` mean "what this process booted with" rather than "what is on disk".
_BOOT_MONOTONIC = time.monotonic()
_BOOT_WALL = datetime.now(timezone.utc)

# manufacturing/version_core.py -> manufacturing/ -> repo root
REPO_DIR = Path(__file__).resolve().parent.parent


def _resolve_git_dir(repo_dir: Path) -> Path | None:
    """Return the real .git directory, following the worktree indirection.

    In a linked worktree `.git` is a FILE containing `gitdir: <path>`, not a
    directory -- so a naive `repo/.git/HEAD` read returns nothing there. The
    deployment clone is a normal checkout, but this module is also imported
    from worktrees during development and silently reporting `None` there
    would make the endpoint look broken while it was merely mislocated.
    """
    git = repo_dir / '.git'
    try:
        if git.is_dir():
            return git
        if git.is_file():
            text = git.read_text(encoding='utf-8', errors='replace').strip()
            if text.startswith('gitdir:'):
                target = Path(text.split(':', 1)[1].strip())
                if not target.is_absolute():
                    target = (repo_dir / target).resolve()
                return target if target.exists() else None
    except OSError:
        return None
    return None


def _common_dir(git_dir: Path) -> Path:
    """Worktrees keep HEAD locally but share refs via the `commondir` pointer."""
    try:
        commondir = git_dir / 'commondir'
        if commondir.is_file():
            target = Path(commondir.read_text(encoding='utf-8').strip())
            if not target.is_absolute():
                target = (git_dir / target).resolve()
            if target.exists():
                return target
    except OSError:
        pass
    return git_dir


def _read_ref(git_dir: Path, ref: str) -> str | None:
    """Resolve a ref name to a SHA: loose file first, then packed-refs."""
    for base in (git_dir, _common_dir(git_dir)):
        try:
            loose = base / ref
            if loose.is_file():
                value = loose.read_text(encoding='utf-8').strip()
                if value:
                    return value
        except OSError:
            pass
        try:
            packed = base / 'packed-refs'
            if packed.is_file():
                for line in packed.read_text(encoding='utf-8', errors='replace').splitlines():
                    line = line.strip()
                    if not line or line.startswith(('#', '^')):
                        continue
                    parts = line.split(None, 1)
                    if len(parts) == 2 and parts[1] == ref:
                        return parts[0]
        except OSError:
            pass
    return None


def read_head(repo_dir: Path | None = None) -> dict:
    """Read HEAD from .git without invoking git. Never raises."""
    result: dict = {'sha': None, 'branch': None}
    git_dir = _resolve_git_dir(Path(repo_dir) if repo_dir else REPO_DIR)
    if git_dir is None:
        return result
    try:
        head = (git_dir / 'HEAD').read_text(encoding='utf-8').strip()
    except OSError:
        return result
    if head.startswith('ref:'):
        ref = head.split(':', 1)[1].strip()
        # Strip the refs/heads/ prefix, NOT everything up to the last slash:
        # branch names routinely contain slashes (feat/x, docs/y) and
        # rsplit('/', 1) silently reports "x" for "feat/x".
        prefix = 'refs/heads/'
        result['branch'] = ref[len(prefix):] if ref.startswith(prefix) else ref
        result['sha'] = _read_ref(git_dir, ref)
    elif head:
        # Detached HEAD -- a raw SHA, and no branch name to report. The
        # deployment clone landed in exactly this state once tonight.
        result['sha'] = head
    return result


# Resolved once, at import.
_BOOT = read_head()


def deploy_info(repo_dir: Path | None = None) -> dict:
    """Version block for the health endpoint. Never raises."""
    try:
        current = read_head(repo_dir)
    except Exception:  # pragma: no cover -- defensive; read_head is total
        current = {'sha': None, 'branch': None}

    boot_sha = _BOOT.get('sha')
    disk_sha = current.get('sha')
    return {
        'sha': boot_sha,
        'short_sha': boot_sha[:7] if boot_sha else None,
        'branch': current.get('branch'),
        'disk_sha': disk_sha,
        # Only meaningful when both are known: a missing SHA is "unknown",
        # not "stale", and must not be reported as a deploy problem.
        'code_stale': bool(boot_sha and disk_sha and boot_sha != disk_sha),
        'started_at': _BOOT_WALL.isoformat().replace('+00:00', 'Z'),
        'uptime_seconds': round(time.monotonic() - _BOOT_MONOTONIC, 1),
    }
