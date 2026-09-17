from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def test_v161_is_additive_and_preserves_frozen_boundaries() -> None:
    src = Path("cfb_game_total_clean_page_v11.py").read_text(encoding="utf-8")
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v10"' in src
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in src
    assert "MAY_MODIFY_PROJECTION = False" in src
    assert 'ODDS_ENDPOINT = "/api/v1/cfb/odds"' in src
    assert 'ODDS_MATCH_METHOD = "official ESPN event_id only"' in src


def test_v161_removes_monster_masthead_but_keeps_dashboard_markers() -> None:
    src = Path("cfb_game_total_clean_page_v11.py").read_text(encoding="utf-8")
    assert "MONSTER SPORTS INTELLIGENCE" not in src
    assert "GAME TOTAL ANALYSIS" in src
    assert "TEAM EVIDENCE" in src
    assert "GAME TOTAL EVIDENCE • STEPS 1–12" in src
    assert "FINAL MODEL SUMMARY" in src
    assert "TOP-5 SLATE SCANNER" in src


def test_v161_day_strip_and_query_persistence_contract() -> None:
    src = Path("cfb_game_total_clean_page_v11.py").read_text(encoding="utf-8")
    assert 'DATE_QUERY_KEY = "ks_cfb_game_total_date"' in src
    assert "def _render_day_strip" in src
    assert "st.query_params[DATE_QUERY_KEY]" in src
    assert "timedelta(days=" in src


def test_verified_market_requires_exact_identity_and_fresh_feed() -> None:
    from cfb_game_total_clean_page_v11 import _verified_market_for_game

    display_game = {
        "event_id": "401900001",
        "game_date": "2026-09-19",
        "away_team": "Away State",
        "home_team": "Home State",
        "away": {"team_id": "11"},
        "home": {"team_id": "22"},
    }
    payload = {
        "captured_at_utc": "2026-09-19T16:00:00+00:00",
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
        "games": [{
            "game_id": "401900001",
            "game_date": "2026-09-19",
            "away_team": "Away State",
            "home_team": "Home State",
            "away_team_id": "11",
            "home_team_id": "22",
            "sportsbook": "FanDuel",
            "total": 56.5,
            "line_status": "open",
            "line_updated_at_utc": "2026-09-19T15:59:30+00:00",
            "identity_verified": True,
        }],
    }
    result = _verified_market_for_game(
        display_game,
        payload,
        now_utc=datetime(2026, 9, 19, 16, 1, tzinfo=timezone.utc),
    )
    assert result["verified"] is True
    assert result["total"] == 56.5
    assert result["sportsbook"] == "FanDuel"
    assert result["projection_weight"] == 0.0


def test_verified_market_fails_closed_on_wrong_game_or_stale_feed() -> None:
    from cfb_game_total_clean_page_v11 import _verified_market_for_game

    display_game = {
        "event_id": "401900001",
        "game_date": "2026-09-19",
        "away_team": "Away State",
        "home_team": "Home State",
        "away": {"team_id": "11"},
        "home": {"team_id": "22"},
    }
    wrong = {
        "captured_at_utc": "2026-09-19T16:00:00+00:00",
        "market_semantics": {"projection_weight": 0.0},
        "games": [{
            "game_id": "DIFFERENT",
            "game_date": "2026-09-19",
            "away_team": "Away State",
            "home_team": "Home State",
            "away_team_id": "11",
            "home_team_id": "22",
            "sportsbook": "FanDuel",
            "total": 56.5,
            "line_status": "open",
            "identity_verified": True,
        }],
    }
    assert _verified_market_for_game(display_game, wrong)["verified"] is False

    stale = dict(wrong)
    stale["games"] = [dict(wrong["games"][0], game_id="401900001")]
    stale["captured_at_utc"] = "2026-09-19T15:00:00+00:00"
    result = _verified_market_for_game(
        display_game,
        stale,
        now_utc=datetime(2026, 9, 19, 16, 1, tzinfo=timezone.utc),
    )
    assert result["verified"] is False
    assert result["total"] is None
