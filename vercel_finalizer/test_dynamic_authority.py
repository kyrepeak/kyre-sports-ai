from __future__ import annotations

from pathlib import Path


def test_finalizer_source_has_no_historical_authority():
    source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
    assert "/pulls/1526" not in source
    assert "ALLOWED_BRANCH" not in source
    assert "resolve_authority" in source
    assert "workstream" in source
    assert "task_id" in source
    assert "fencing_generation" in source


def test_dynamic_authority_explicitly_excludes_superseded_history():
    source = Path(__file__).with_name("authority.py").read_text(encoding="utf-8")
    assert "SUPERSEDED_BASE_DRIFT" in source
    assert "FINALIZER_AUTHORITY_SUPERSEDED" in source
    assert "order by created_at desc" not in source.lower()
    assert "newest" not in source.lower()
