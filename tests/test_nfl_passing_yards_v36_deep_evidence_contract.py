from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V36 = ROOT / "nfl_passing_yards_hub_v36.py"


def test_v36_deep_evidence_keeps_all_certified_step_surfaces_available() -> None:
    source = V36.read_text(encoding="utf-8")

    assert "def _deep_evidence_html" in source
    assert "<details" in source
    assert "<summary" in source

    for key in (
        "identity",
        "profile",
        "defense",
        "pressure",
        "personnel",
        "environment",
        "projection",
        "context",
        "distribution",
        "market",
    ):
        assert f'_piece(captured, "{key}"' in source


def test_v36_renders_deep_evidence_for_both_quarterbacks() -> None:
    source = V36.read_text(encoding="utf-8")

    assert "Passing Profile" in source
    assert "Opponent Pass Defense" in source
    assert "Pressure + Protection" in source
    assert "Personnel + Availability" in source
    assert "Game Environment" in source
    assert "Projection Recipe" in source
    assert "Uncertainty + Context" in source
    assert "Distribution + Probability" in source
    assert "Market Math" in source
    assert "_deep_evidence_html(captured, 0)" in source
    assert "_deep_evidence_html(captured, 1)" in source
