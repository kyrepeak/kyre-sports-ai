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
