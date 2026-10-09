from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "cfb_game_total_page2_step2_matchup_hero_phx_v1.py"


def _load_module():
    assert MODULE.exists(), "Page-2 Step-2 matchup hero module must exist"
    spec = importlib.util.spec_from_file_location("page2_step2_matchup_hero", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step2_page2_module_exists() -> None:
    assert MODULE.exists(), "Page-2 Step-2 matchup hero module must exist"


def test_step2_uses_phoenix_time_contract() -> None:
    module = _load_module()
    assert module.PHOENIX_TZ == "America/Phoenix"
    day_label, time_label = module.phoenix_kickoff_parts(
        {"kickoff_iso": "2026-10-10T00:30:00Z"}
    )
    assert day_label == "Fri • Oct 9"
    assert time_label == "5:30 PM AZ"


def test_step2_builds_dynamic_page2_matchup_hero() -> None:
    module = _load_module()
    html = module.build_page2_matchup_hero_html(
        identity={
            "away": {"team": "Texas Longhorns", "conference": "SEC"},
            "home": {"team": "Oklahoma Sooners", "conference": "SEC"},
        },
        away={"record": "6-1"},
        home={"record": "5-2"},
        display_game={
            "kickoff_iso": "2026-10-10T00:30:00Z",
            "venue": "Cotton Bowl",
            "venue_location": "Dallas, TX",
        },
        away_logo_html='<img src="away.png" alt="Texas">',
        home_logo_html='<img src="home.png" alt="Oklahoma">',
        total_line=56.5,
        confidence_label="High Confidence",
    )
    for token in (
        'data-testid="gtp2s2-matchup-hero"',
        'data-testid="gtp2s2-total-line"',
        'data-testid="gtp2s2-confidence"',
        'data-timezone="America/Phoenix"',
        "Texas Longhorns",
        "Oklahoma Sooners",
        "6-1",
        "5-2",
        "Cotton Bowl",
        "Dallas, TX",
        "56.5",
        "High Confidence",
        "Fri • Oct 9",
        "5:30 PM AZ",
        "Page 2 of 2",
    ):
        assert token in html


def test_step2_is_presentation_only_and_does_not_reopen_page1() -> None:
    module = _load_module()
    source = MODULE.read_text(encoding="utf-8")
    assert module.MAY_MODIFY_PROJECTION is False
    assert module.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert module.MAY_MODIFY_PAGE1 is False
    assert module.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert module.NETWORK_CALLS_ADDED == 0
    assert "requests" not in source
    assert "httpx" not in source
    assert "Texas Longhorns" not in source
    assert "Oklahoma Sooners" not in source
    assert "56.5" not in source
