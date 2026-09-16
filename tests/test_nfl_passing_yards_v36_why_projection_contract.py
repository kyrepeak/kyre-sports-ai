from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V36 = ROOT / "nfl_passing_yards_hub_v36.py"


def test_v36_why_projection_reuses_certified_rendered_evidence() -> None:
    source = V36.read_text(encoding="utf-8")

    assert "def _semantic_tone" in source
    assert "def _why_projection_html" in source
    for label in ("Volume", "Efficiency", "Pressure", "Personnel", "Weather"):
        assert label in source
    for rendered_class in ("kpy-projhero", "kpy-xgrade", "kpy-ilabel", "kpy-envmetrics"):
        assert rendered_class in source


def test_v36_has_approved_semantic_color_system() -> None:
    source = V36.read_text(encoding="utf-8")

    for tone in (
        "tone-positive",
        "tone-negative",
        "tone-caution",
        "tone-info",
        "tone-model",
        "tone-muted",
    ):
        assert tone in source

    assert "_why_projection_html(captured, 0)" in source
    assert "_why_projection_html(captured, 1)" in source
