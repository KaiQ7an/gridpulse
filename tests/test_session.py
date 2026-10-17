import json
import time

from gridpulse import session


def test_archive_refusals_are_remembered_for_a_while(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "REFUSALS", tmp_path / "refusals.json")
    assert not session.refused_recently("2026-15-R")
    session.remember_refusal("2026-15-R")
    assert session.refused_recently("2026-15-R")
    assert not session.refused_recently("2026-16-R")
    # Older than the time limit: try the archive again.
    old = time.time() - (session.REFUSAL_TTL_HOURS + 1) * 3600
    (tmp_path / "refusals.json").write_text(json.dumps({"2026-15-R": old}))
    assert not session.refused_recently("2026-15-R")


def test_hosted_flag(monkeypatch):
    from gridpulse import deploy

    monkeypatch.setenv("GRIDPULSE_HOSTED", "1")
    assert deploy.hosted()
    monkeypatch.setenv("GRIDPULSE_HOSTED", "0")
    assert not deploy.hosted()
