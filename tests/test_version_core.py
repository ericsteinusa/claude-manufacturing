"""Tests for version_core — deploy identity read straight from .git.

The point of the module is telling "what this process booted with" apart from
"what is on disk now", so most of these build a throwaway .git by hand and
assert the resolution rules, including the worktree and packed-refs shapes
that a naive `.git/HEAD` read gets wrong.
"""

import manufacturing.version_core as version_core
from manufacturing.version_core import deploy_info, read_head

SHA_A = "09a69e4aaa907e2fde2cb28fcd2f681e773b5deb"
SHA_B = "ebe39e320ce582986c97458a56f1f1f9b57fb971"


def _make_repo(tmp_path, head_text, refs=None, packed=None, commondir=None):
    """Build a minimal .git directory."""
    repo = tmp_path / "repo"
    git = repo / ".git"
    git.mkdir(parents=True)
    (git / "HEAD").write_text(head_text)
    for name, sha in (refs or {}).items():
        p = git / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(sha + "\n")
    if packed is not None:
        (git / "packed-refs").write_text(packed)
    if commondir is not None:
        (git / "commondir").write_text(commondir)
    return repo


# ── HEAD resolution ────────────────────────────────────────────────────────

def test_reads_branch_head_from_loose_ref(tmp_path):
    repo = _make_repo(tmp_path, "ref: refs/heads/main\n",
                      refs={"refs/heads/main": SHA_A})
    assert read_head(repo) == {"sha": SHA_A, "branch": "main"}


def test_branch_name_containing_a_slash_is_kept_whole(tmp_path):
    # Regression: rsplit('/', 1) reported "healthz-version-endpoint" for
    # refs/heads/feat/healthz-version-endpoint. Every branch in this repo is
    # of the form feat/x or docs/y, so the naive split was wrong for nearly
    # all of them -- and the unit tests missed it because they all used
    # single-segment names.
    repo = _make_repo(tmp_path, "ref: refs/heads/feat/healthz-version-endpoint\n",
                      refs={"refs/heads/feat/healthz-version-endpoint": SHA_A})
    assert read_head(repo) == {"sha": SHA_A, "branch": "feat/healthz-version-endpoint"}


def test_detached_head_reports_sha_and_no_branch(tmp_path):
    # The deployment clone landed in exactly this state during the incident.
    repo = _make_repo(tmp_path, SHA_A + "\n")
    assert read_head(repo) == {"sha": SHA_A, "branch": None}


def test_falls_back_to_packed_refs_when_loose_ref_absent(tmp_path):
    # A freshly cloned/gc'd repo has no loose ref file at all.
    repo = _make_repo(
        tmp_path, "ref: refs/heads/main\n",
        packed=f"# pack-refs with: peeled fully-peeled sorted\n{SHA_B} refs/heads/main\n",
    )
    assert read_head(repo)["sha"] == SHA_B


def test_packed_refs_ignores_peeled_and_comment_lines(tmp_path):
    repo = _make_repo(
        tmp_path, "ref: refs/heads/main\n",
        packed=(
            "# pack-refs with: peeled\n"
            f"{SHA_A} refs/tags/v1\n"
            f"^{SHA_B}\n"
            f"{SHA_B} refs/heads/main\n"
        ),
    )
    assert read_head(repo)["sha"] == SHA_B


def test_loose_ref_wins_over_packed_refs(tmp_path):
    repo = _make_repo(tmp_path, "ref: refs/heads/main\n",
                      refs={"refs/heads/main": SHA_A},
                      packed=f"{SHA_B} refs/heads/main\n")
    assert read_head(repo)["sha"] == SHA_A


def test_worktree_git_file_is_followed(tmp_path):
    # In a linked worktree `.git` is a FILE ("gitdir: <path>"), so a naive
    # repo/.git/HEAD read finds nothing.
    real = tmp_path / "realgit"
    (real / "refs" / "heads").mkdir(parents=True)
    (real / "HEAD").write_text("ref: refs/heads/feature\n")
    (real / "refs" / "heads" / "feature").write_text(SHA_B + "\n")
    repo = tmp_path / "wt"
    repo.mkdir()
    (repo / ".git").write_text(f"gitdir: {real}\n")
    assert read_head(repo) == {"sha": SHA_B, "branch": "feature"}


def test_worktree_resolves_shared_refs_via_commondir(tmp_path):
    # Worktrees keep their own HEAD but share refs through `commondir`.
    common = tmp_path / "common"
    (common / "refs" / "heads").mkdir(parents=True)
    (common / "refs" / "heads" / "main").write_text(SHA_A + "\n")
    wt_git = tmp_path / "repo" / ".git"
    wt_git.mkdir(parents=True)
    (wt_git / "HEAD").write_text("ref: refs/heads/main\n")
    (wt_git / "commondir").write_text(str(common) + "\n")
    assert read_head(tmp_path / "repo")["sha"] == SHA_A


# ── degradation: a health probe must never 500 ─────────────────────────────

def test_missing_git_returns_nulls_not_an_exception(tmp_path):
    plain = tmp_path / "nogit"
    plain.mkdir()
    assert read_head(plain) == {"sha": None, "branch": None}


def test_unreadable_ref_returns_none_sha(tmp_path):
    repo = _make_repo(tmp_path, "ref: refs/heads/main\n")  # ref never written
    assert read_head(repo) == {"sha": None, "branch": "main"}


def test_deploy_info_survives_a_broken_repo(tmp_path):
    plain = tmp_path / "nogit"
    plain.mkdir()
    info = deploy_info(plain)
    assert info["sha"] is None or isinstance(info["sha"], str)
    assert info["code_stale"] is False
    assert info["uptime_seconds"] >= 0


# ── the point of the module: stale detection ───────────────────────────────

def test_code_stale_true_when_disk_moved_past_the_running_process(tmp_path, monkeypatch):
    # The pulled-but-not-restarted window: the repo advanced, this process
    # is still serving the commit it booted with.
    monkeypatch.setattr(version_core, "_BOOT", {"sha": SHA_B, "branch": "main"})
    repo = _make_repo(tmp_path, "ref: refs/heads/main\n",
                      refs={"refs/heads/main": SHA_A})
    info = deploy_info(repo)
    assert info["code_stale"] is True
    assert info["sha"] == SHA_B          # what is being SERVED
    assert info["disk_sha"] == SHA_A     # what is on disk
    assert info["short_sha"] == SHA_B[:7]


def test_code_stale_false_when_they_match(tmp_path, monkeypatch):
    monkeypatch.setattr(version_core, "_BOOT", {"sha": SHA_A, "branch": "main"})
    repo = _make_repo(tmp_path, "ref: refs/heads/main\n",
                      refs={"refs/heads/main": SHA_A})
    assert deploy_info(repo)["code_stale"] is False


def test_unknown_sha_is_not_reported_as_stale(tmp_path, monkeypatch):
    # "I could not read it" must not masquerade as "the deploy is broken" --
    # the same confusion as a kill-failure count of 0 meaning both "nothing
    # to kill" and "not allowed to look".
    monkeypatch.setattr(version_core, "_BOOT", {"sha": None, "branch": None})
    repo = _make_repo(tmp_path, "ref: refs/heads/main\n",
                      refs={"refs/heads/main": SHA_A})
    assert deploy_info(repo)["code_stale"] is False


def test_started_at_is_utc_iso_z(tmp_path):
    info = deploy_info(tmp_path)
    assert info["started_at"].endswith("Z")
    assert "T" in info["started_at"]
