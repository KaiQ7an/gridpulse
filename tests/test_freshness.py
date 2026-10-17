"""After an update lands in a running server, the app must load the new code, not keep the old modules."""

import pytest

from gridpulse.pitwall.freshness import LOADED, commit, forget_stale_modules

OLD, NEW = "a" * 40, "b" * 40


def checkout(root, sha, *, packed=False):
    git = root / ".git"
    (git / "refs" / "heads").mkdir(parents=True, exist_ok=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    if packed:
        (git / "packed-refs").write_text(f"# pack-refs with: peeled\n{sha} refs/heads/main\n")
    else:
        (git / "refs" / "heads" / "main").write_text(sha + "\n")
    return root


def test_commit_is_read_from_the_checkout(tmp_path):
    assert commit(tmp_path) is None  # not a git checkout
    assert commit(checkout(tmp_path / "loose", OLD)) == OLD
    assert commit(checkout(tmp_path / "packed", NEW, packed=True)) == NEW
    detached = tmp_path / "detached" / ".git"
    detached.mkdir(parents=True)
    (detached / "HEAD").write_text(NEW + "\n")
    assert commit(detached.parent) == NEW


def test_commit_in_a_worktree(tmp_path):
    main = checkout(tmp_path / "main", OLD) / ".git"
    tree = main / "worktrees" / "wt"
    tree.mkdir(parents=True)
    (tree / "HEAD").write_text("ref: refs/heads/main\n")
    (tree / "commondir").write_text("../..\n")
    (tmp_path / "wt").mkdir()
    (tmp_path / "wt" / ".git").write_text(f"gitdir: {tree}\n")
    assert commit(tmp_path / "wt") == OLD


@pytest.fixture
def loaded(monkeypatch):
    monkeypatch.delenv(LOADED, raising=False)
    return {"gridpulse": 1, "gridpulse.pitwall": 1, "gridpulse.pitwall.freshness": 1, "gridpulse.pitwall.ui": 1,
            "gridpulse.season.data": 1, "pandas": 1, "gridpulseish": 1}


def forget(root, modules, hosted=False):
    cleared = []
    did = forget_stale_modules(root, hosted=hosted, modules=modules, clear=lambda: cleared.append(True))
    assert did == bool(cleared)
    return did


def test_new_commit_forgets_every_gridpulse_module_and_the_caches(tmp_path, loaded):
    root = checkout(tmp_path, OLD)
    assert not forget(root, loaded)  # first run: the modules were loaded at this commit
    assert not forget(root, loaded)  # every later run at the same commit
    checkout(tmp_path, NEW)  # Community Cloud pulls a new commit into the running server
    assert forget(root, loaded)
    assert sorted(loaded) == ["gridpulseish", "pandas"]
    assert not forget(root, loaded)


def test_on_a_server_modules_from_before_this_check_are_forgotten(tmp_path, loaded):
    root = checkout(tmp_path, NEW)
    assert forget(root, loaded, hosted=True)  # gridpulse.pitwall.ui was already loaded: unknown commit
    assert sorted(loaded) == ["gridpulseish", "pandas"]


def test_a_fresh_server_keeps_what_this_check_just_imported(tmp_path, monkeypatch):
    monkeypatch.delenv(LOADED, raising=False)
    fresh = {"gridpulse": 1, "gridpulse.pitwall": 1, "gridpulse.pitwall.freshness": 1}
    assert not forget(checkout(tmp_path, NEW), fresh, hosted=True)
    assert len(fresh) == 3


def test_outside_a_checkout_nothing_happens(tmp_path, loaded):
    assert not forget(tmp_path, loaded, hosted=True)
    assert len(loaded) == 7
