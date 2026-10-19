from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nba_spread_page_v7.py"
LOADER = ROOT / "universal_runtime_v5_loader_v22.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v6.py"
APP = ROOT / "app.py"


def _game(date: str, away: str, home: str, status: str = "UPCOMING") -> dict:
    return {
        "game_key": f"{date}:{away}:{home}",
        "game_date_phoenix": date,
        "away_tricode": away,
        "home_tricode": home,
        "away_name": away,
        "home_name": home,
        "tip_phoenix": "4:00 PM MST",
        "status": status,
        "venue": "Arena",
    }


def test_v7_is_additive_launch_ready_presentation_over_frozen_step10_stack() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "import nba_spread_page_v6 as live_repair_page" in source
    assert "import nba_spread_page_v5 as step10_page" in source
    assert 'FROZEN_PARENT_PAGE = "nba_spread_page_v6"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "decorate_and_rank_games" not in source
    assert "build_fair_spread_context" not in source


def test_next_active_slate_returns_only_earliest_upcoming_date() -> None:
    page = importlib.import_module("nba_spread_page_v7")
    games = [
        _game("2026-10-21", "MIL", "WAS"),
        _game("2026-10-20", "BOS", "DET"),
        _game("2026-10-20", "PHI", "NYK"),
        _game("2026-10-19", "LAL", "GSW", "FINAL"),
    ]
    slate_date, slate = page._next_active_slate_games(games)
    assert slate_date == "2026-10-20"
    assert [(g["away_tricode"], g["home_tricode"]) for g in slate] == [("BOS", "DET"), ("PHI", "NYK")]


def test_market_context_is_per_game_and_requires_verified_observations() -> None:
    page = importlib.import_module("nba_spread_page_v7")
    games = [_game("2026-10-20", "BOS", "DET"), _game("2026-10-20", "PHI", "NYK")]
    payload = {
        "verification": "VERIFIED",
        "observations": [
            {"away_tricode": "BOS", "home_tricode": "DET", "sportsbook": "FanDuel", "away_spread": -4.0, "home_spread": 4.0},
            {"away_tricode": "BOS", "home_tricode": "DET", "sportsbook": "DraftKings", "away_spread": -3.5, "home_spread": 3.5},
        ],
    }
    market = page._market_by_game(games, payload)
    assert market[("BOS", "DET")]["verification"] == "VERIFIED"
    assert market[("BOS", "DET")]["sportsbook_count"] == 2
    assert market[("PHI", "NYK")]["verification"] == "UNAVAILABLE"
    assert market[("PHI", "NYK")]["diagnostic_state"] in {
        "NO_VERIFIED_SCHEDULE_MATCH",
        "CONSENSUS_QUORUM_NOT_MET",
    }


def test_compact_injury_summary_replaces_full_injury_cards() -> None:
    page = importlib.import_module("nba_spread_page_v7")
    feature = {
        "verification": "VERIFIED",
        "away": {"counts": {"OUT": 0, "QUESTIONABLE": 1}},
        "home": {"counts": {"OUT": 0, "QUESTIONABLE": 0}},
    }
    text, state = page._injury_summary(feature)
    assert state == "watch"
    assert "1 questionable" in text.lower()
    assert "No listed players from the verified current snapshot" not in text


def test_compact_game_card_prioritizes_matchup_market_model_and_status() -> None:
    page = importlib.import_module("nba_spread_page_v7")
    game = _game("2026-10-20", "BOS", "DET")
    game["step9_fair_spread"] = {
        "verification": "VERIFIED",
        "pregame_model": {
            "fair_away_spread": -5.0,
            "fair_home_spread": 5.0,
            "away_cover_probability": 0.57,
            "home_cover_probability": 0.43,
            "cover_verification": "VERIFIED",
        },
    }
    game["step10_decision"] = {
        "verification": "VERIFIED",
        "decision_state": "PLAY",
        "pick_text": "BOS -3.5",
        "selected_cover_probability_no_push": 0.58,
        "cover_edge_pp": 8.0,
        "pick_strength": "STRONG",
        "production_grade": "A",
    }
    market = {"verification": "VERIFIED", "consensus_away_spread": -3.5, "consensus_home_spread": 3.5, "sportsbook_count": 2}
    injury = {"verification": "VERIFIED", "away": {"counts": {}}, "home": {"counts": {}}}
    html = page._compact_game_card(game, market, injury)
    for expected in ("BOS @ DET", "Market", "Kyre Fair Spread", "Cover Probability", "MODEL LEAN", "BOS -3.5"):
        assert expected in html
    for forbidden in ("STEP9_VERIFIED_MODEL_REQUIRED", "PREGAME_MODEL_MISSING", "No listed players from the verified current snapshot"):
        assert forbidden not in html


def test_page_removes_permanent_unavailable_graveyard_and_full_injury_wall() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "NEXT NBA SLATE" in source
    assert "MARKET DATA STATUS" in source
    assert "BEST OPPORTUNITIES" in source
    assert 'with st.expander("Sources & Diagnostics", expanded=False):' in source
    assert "_render_injury_section" not in source
    assert "Most Bet Game data unavailable" not in source
    assert "Sharp Money Game data unavailable" not in source
    assert "Market Spread data unavailable" not in source
    assert "No listed players from the verified current snapshot" not in source


def test_loader_v22_routes_only_nba_spread_to_v7() -> None:
    source = LOADER.read_text(encoding="utf-8")
    assert "import universal_runtime_v5_loader_v21 as prior" in source
    assert 'route.sport_id == "nba" and route.market_id == "spread"' in source
    assert 'importlib.import_module("nba_spread_page_v7")' in source
    assert 'importlib.import_module("nba_spread_page_provider_resilience_step3_r1")' in source
    assert "return prior.resolve_destination(route)" in source


def test_terminal_and_app_advance_only_runtime_loader_handoff() -> None:
    source = TERMINAL.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_universal_runtime_v5 as prior" in source
    assert "from universal_runtime_v5_loader_v22 import choose_prefetch, load_destination, resolve_destination" in source
    assert "prior.choose_prefetch = choose_prefetch" in source
    assert "prior.load_destination = load_destination" in source
    assert "prior.resolve_destination = resolve_destination" in source
    assert "return prior.render_app()" in source
    app_source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v6" in app_source
