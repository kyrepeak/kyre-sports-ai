from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V36 = ROOT / "nfl_passing_yards_hub_v36.py"


def test_v36_builds_matchup_header_and_qb_hero_from_certified_rendered_evidence() -> None:
    source = V36.read_text(encoding="utf-8")

    assert "import nfl_passing_yards_hub_v34 as composition" in source
    assert "def _matchup_header_html" in source
    assert "def _qb_hero_card_html" in source
    assert "def _compact_dashboard_html" in source
    assert 'nfl_passing_yards_v8_matchup' in source

    # Reuse certified rendered identity/projection/market surfaces; do not
    # recalculate values in V36.
    for rendered_class in (
        "kpass29-logo",
        "kpass29-top",
        "kpy-projhero",
        "kpy10-hero",
        "kpy10-metrics",
    ):
        assert rendered_class in source


def test_v36_temporarily_replaces_only_v34_presentation_composer_and_restores_it() -> None:
    source = V36.read_text(encoding="utf-8")

    assert "original_composer = composition._combined_player_cards_html" in source
    assert "composition._combined_player_cards_html = _compact_dashboard_html" in source
    assert "composition._combined_player_cards_html = original_composer" in source
    assert "finally:" in source
