from __future__ import annotations

from pathlib import Path

import cfb_top_picks_details_v1 as details
import cfb_top_picks_page_v4 as page


PAGE = Path("cfb_top_picks_page_v4.py").read_text(encoding="utf-8")
ROUTER = Path("streamlit_memory_lazy_router_v244.py").read_text(encoding="utf-8")
APP = Path("app.py").read_text(encoding="utf-8")


def _row(**overrides):
    row = {
        "rank": 1,
        "event_id": "401234567",
        "away": "Away State",
        "away_abbr": "AWY",
        "home": "Home Tech",
        "home_abbr": "HME",
        "time": "Sat, 12:00 PM",
        "network": "ESPN",
        "market": "MONEYLINE",
        "pick": "Away State",
        "odds": "-145",
        "probability": 68,
        "probability_value": 0.68,
        "toughness": 3,
        "toughness_label": "Medium",
        "reliability": 0.82,
        "source": "Kyre Moneyline model",
        "sportsbook_projection_weight": 0.0,
    }
    row.update(overrides)
    return row


def _game():
    return {
        "espn_event_id": "401234567",
        "game_id": "401234567",
        "game_date": "2026-10-03",
        "away_team": "Away State",
        "home_team": "Home Tech",
        "away_espn_team_id": "101",
        "home_espn_team_id": "202",
        "identity_verified": True,
        "date_matches_query": True,
    }


def _series():
    return {
        "ready": True,
        "source": "Winsipedia",
        "source_url": "https://www.winsipedia.com/games/away-state/vs/home-tech",
        "meetings": 4,
        "away_wins": 3,
        "home_wins": 1,
        "ties": 0,
        "avg_combined_total": 57.5,
        "latest": {
            "date": "2025-10-04",
            "away_points": 31,
            "home_points": 24,
            "combined_total": 55,
        },
        "sample": [
            {"date": "2025-10-04", "away_points": 31, "home_points": 24, "combined_total": 55},
            {"date": "2024-10-05", "away_points": 28, "home_points": 21, "combined_total": 49},
            {"date": "2023-10-07", "away_points": 35, "home_points": 27, "combined_total": 62},
            {"date": "2022-10-01", "away_points": 17, "home_points": 20, "combined_total": 37},
        ],
    }


def test_step4_detail_requires_exact_verified_event_and_team_ids(monkeypatch):
    monkeypatch.setattr(details.schedule, "games_for_date", lambda day: [_game()])
    monkeypatch.setattr(details.history_recovery, "_fetch_winsipedia_games", lambda away, home: _series())

    out = details.build_pick_detail(_row(), "2026-10-03")

    assert out["ready"] is True
    assert out["event_id"] == "401234567"
    assert out["away_espn_team_id"] == "101"
    assert out["home_espn_team_id"] == "202"
    assert out["history_ready"] is True
    assert out["meetings"] == 4
    assert len(out["history_rows"]) == 3
    assert "3-1" in out["benefit"]


def test_step4_fails_closed_when_exact_event_identity_is_ambiguous(monkeypatch):
    duplicate = dict(_game())
    monkeypatch.setattr(details.schedule, "games_for_date", lambda day: [_game(), duplicate])

    called = {"history": False}

    def _history(*args, **kwargs):
        called["history"] = True
        return _series()

    monkeypatch.setattr(details.history_recovery, "_fetch_winsipedia_games", _history)
    out = details.build_pick_detail(_row(), "2026-10-03")

    assert out["ready"] is False
    assert out["history_ready"] is False
    assert called["history"] is False
    assert "no historical claim" in out["benefit"].lower()


def test_step4_over_under_benefit_is_descriptive_only(monkeypatch):
    monkeypatch.setattr(details.schedule, "games_for_date", lambda day: [_game()])
    monkeypatch.setattr(details.history_recovery, "_fetch_winsipedia_games", lambda away, home: _series())

    out = details.build_pick_detail(
        _row(market="OVER/UNDER", pick="Over 54.5", probability=63),
        "2026-10-03",
    )

    assert "57.5" in out["benefit"]
    assert "54.5" in out["benefit"]
    assert out["history_projection_weight"] == 0.0
    assert out["history_selection_weight"] == 0.0
    assert out["history_ranking_weight"] == 0.0
    assert out["sportsbook_projection_weight"] == 0.0


def test_step4_page_is_collapsed_by_default_and_contains_three_detail_sections():
    html = page._detail_card(
        _row(),
        {
            "why": "Why text",
            "benefit": "Benefit text",
            "event_id": "401234567",
            "meetings": 0,
            "history_rows": [],
        },
    )
    assert "<details" in html
    assert 'data-expanded="false"' in html
    assert "Why This Pick" in html
    assert "Actual Matchup History" in html
    assert "Benefits" in html
    assert "history projection weight <strong>0.0%</strong>" in html


def test_step4_preserves_frozen_step3_ranked_engine_and_zero_weights():
    assert "engine.build_top_picks(limit=10)" in PAGE
    assert "CFB_TOP_PICKS_STEP3_LIVE_RANKING_ACTIVE" in PAGE
    assert "Tap a matchup for Why • History • Benefits" in PAGE
    assert "SAMPLE_LAYOUT_ROWS" not in PAGE
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.HISTORY_PROJECTION_INFLUENCE == 0.0
    assert details.HISTORY_PROJECTION_WEIGHT == 0.0


def test_router_v244_is_additive_over_frozen_v243():
    assert "import streamlit_memory_lazy_router_v243 as prior" in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v243"' in ROUTER
    assert 'TOP_PICKS_PAGE = "cfb_top_picks_page_v4"' in ROUTER
    assert "return prior.render_app()" in ROUTER
    assert "MAY_MODIFY_EXISTING_CFB_PRODUCTS = False" in ROUTER
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in ROUTER
    assert "HISTORY_PROJECTION_INFLUENCE = 0.0" in ROUTER


def test_app_activates_v244_and_keeps_v243_as_frozen_parent():
    assert "from streamlit_memory_lazy_router_v244 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen V243 compatibility" in APP
