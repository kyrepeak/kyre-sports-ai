"""Regression checks for College Football Step 4 Moneyline page UI."""
from __future__ import annotations

import inspect

import cfb_moneyline_hub_v1 as hub


def _profile(team, conference, rank, record, grade="READY", games=3):
    return {
        "team": team,
        "conference": conference,
        "ap_rank": rank,
        "record_text": record,
        "record": {"games": games},
        "data_quality": {"grade": grade},
    }


def _game():
    return {
        "identity_verified": True,
        "date_matches_query": True,
        "away_team": "Ohio State",
        "away_conference": "big-ten",
        "home_team": "Texas",
        "home_conference": "sec",
        "kickoff_et": "7:30 PM ET",
        "venue": "DKR-Texas Memorial Stadium",
        "status": "Scheduled",
        "broadcast": "ABC",
    }


def test_moneyline_hero_has_verified_identity_and_both_teams():
    html = hub._moneyline_hero(
        _game(),
        _profile("Ohio State", "big-ten", 1, "3-0"),
        _profile("Texas", "sec", 5, "2-1"),
    )

    assert "SELECTED MONEYLINE MATCHUP" in html
    assert "IDENTITY VERIFIED" in html
    assert "#1 AP" in html
    assert "Ohio State" in html
    assert "#5 AP" in html
    assert "Texas" in html
    assert "7:30 PM ET" in html
    assert "DKR-Texas Memorial Stadium" in html


def test_readiness_panel_reports_identity_team_quality_and_sample_sizes():
    html = hub._readiness_panel(
        _game(),
        _profile("Ohio State", "big-ten", 1, "3-0", "READY", 3),
        _profile("Texas", "sec", 5, "2-1", "LIMITED", 3),
    )

    assert "MONEYLINE PAGE READINESS" in html
    assert "Game identity" in html
    assert "Away team data" in html
    assert "Home team data" in html
    assert "READY" in html
    assert "LIMITED" in html
    assert "3 / 3" in html


def test_model_locked_panel_explicitly_blocks_unbuilt_outputs():
    html = hub._model_locked_panel()
    assert "MONEYLINE OUTPUT RESERVED" in html
    assert "winner probability" in html
    assert "fair moneyline" in html
    assert "projected score" in html
    assert "simulation" in html


def test_non_moneyline_pages_delegate_to_frozen_step3(monkeypatch):
    seen = []

    def fake_render(market, section_header, status_info, team_logo, h):
        seen.append((market, section_header, status_info, team_logo, h))

    monkeypatch.setattr(hub.frozen_v3, "render_cfb_hub", fake_render)

    hub.render_cfb_hub("Over/Under", "S", "I", "L", "H")
    hub.render_cfb_hub("Game Total", "S2", "I2", "L2", "H2")

    assert seen == [
        ("Over/Under", "S", "I", "L", "H"),
        ("Game Total", "S2", "I2", "L2", "H2"),
    ]


def test_step4_is_moneyline_presentation_only():
    source = inspect.getsource(hub)

    assert hub.FROZEN_CFB_HUB == "cfb_hub_v3"
    assert hub.MARKET == "Moneyline"

    required = (
        "schedule.load_with_diagnostics",
        "team_data.load_matchup_team_data",
        "frozen_v3._team_card",
        "frozen_v3._team_data_diagnostics",
    )
    for token in required:
        assert token in source

    forbidden = (
        "import numpy",
        "np.random",
        "def simulate",
        "def win_probability",
        "fair_odds =",
        "fair_moneyline =",
        "projected_score =",
        "moneyline_pick =",
        "sportsbook_line =",
    )
    for token in forbidden:
        assert token not in source
