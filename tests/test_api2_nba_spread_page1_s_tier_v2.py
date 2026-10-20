from __future__ import annotations

import importlib
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 20, 0, 30, 0, tzinfo=timezone.utc)


def _module(name: str):
    spec = importlib.util.find_spec(name)
    assert spec is not None, f"{name} must exist"
    return importlib.import_module(name)


def _game():
    return {
        "game_key": "PHI@NYK:2026-10-20",
        "game_date_phoenix": "2026-10-20",
        "away_tricode": "PHI",
        "home_tricode": "NYK",
        "away_name": "Philadelphia 76ers",
        "home_name": "New York Knicks",
        "status": "UPCOMING",
        "tip_phoenix": "4:00 PM MST",
        "venue": "Madison Square Garden",
        "step9_fair_spread": {
            "verification": "VERIFIED",
            "pregame_model": {
                "verification": "VERIFIED",
                "cover_verification": "VERIFIED",
                "fair_away_spread": 2.1,
                "fair_home_spread": -2.1,
                "away_cover_probability": 0.61,
                "home_cover_probability": 0.39,
                "market_home_spread": -4.5,
                "sportsbook_projection_influence": 0.0,
            },
        },
        "step10_decision": {
            "verification": "VERIFIED",
            "decision_state": "PLAY",
            "pick_text": "PHI +4.5",
            "pick_strength": "STRONG",
            "production_grade": "A",
            "slate_rank": 1,
            "spread_edge_points": 2.4,
        },
    }


def _row(book: str, away: float, home: float, *, source="SportsGameOdds", open_away=None, open_home=None, away_price=-110, home_price=-110):
    return {
        "game_key": "PHI@NYK:2026-10-20",
        "game_date_phoenix": "2026-10-20",
        "away_tricode": "PHI",
        "home_tricode": "NYK",
        "sportsbook": book,
        "away_spread": away,
        "home_spread": home,
        "away_price": away_price,
        "home_price": home_price,
        "open_away_spread": open_away,
        "open_home_spread": open_home,
        "observed_at_utc": "2026-10-20T00:29:30Z",
        "retrieved_at_utc": "2026-10-20T00:29:35Z",
        "source_transport": source,
    }


def test_s_tier_successor_modules_exist_without_claiming_parallel_v25_path():
    for name in (
        "nba_spread_sportsbook_observations_v3",
        "nba_spread_live_data_repair_v3",
        "nba_spread_decision_board_data_v2",
        "nba_spread_page_v9",
        "universal_runtime_v5_loader_nba_spread_stier_v2",
    ):
        _module(name)
    assert not (ROOT / "universal_runtime_v5_loader_v25.py").exists(), "this workstream must not own the parallel lane's V25 path"


def test_v3_market_transport_requests_major_books_and_true_open_line_fields():
    mod = _module("nba_spread_sportsbook_observations_v3")
    for book in ("fanduel", "draftkings", "betmgm", "caesars", "pinnacle"):
        assert book in mod.DEFAULT_BOOKMAKERS
    assert mod.INCLUDE_OPEN_CLOSE_ODDS is True
    assert mod.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_multisource_bridge_gap_fills_books_without_duplicate_book_rows():
    mod = _module("nba_spread_live_data_repair_v3")
    primary = {"verification": "VERIFIED", "source": "SportsGameOdds", "observations": [_row("FanDuel", 4.5, -4.5), _row("DraftKings", 4.5, -4.5)]}
    secondary = {"verification": "VERIFIED", "source": "Odds-API.io", "observations": [_row("DraftKings", 5.0, -5.0, source="Odds-API.io"), _row("BetMGM", 4.0, -4.0, source="Odds-API.io")]}
    out = mod.combine_verified_market_payloads([_game()], primary, secondary)
    assert out["verification"] == "VERIFIED"
    assert out["source_chain"][:2] == ["SportsGameOdds", "Odds-API.io"]
    books = [row["sportsbook"] for row in out["observations"]]
    assert books.count("DraftKings") == 1
    assert set(books) == {"FanDuel", "DraftKings", "BetMGM"}
    assert out["sportsbook_projection_influence"] == 0.0


def test_market_intelligence_exposes_consensus_best_lines_quotes_and_open_to_current_movement():
    mod = _module("nba_spread_decision_board_data_v2")
    payload = {
        "verification": "VERIFIED",
        "source_chain": ["SportsGameOdds", "Odds-API.io"],
        "observations": [
            _row("FanDuel", 4.5, -4.5, open_away=3.5, open_home=-3.5, away_price=-108),
            _row("DraftKings", 4.5, -4.5, open_away=3.5, open_home=-3.5, away_price=-110),
            _row("BetMGM", 4.0, -4.0, source="Odds-API.io", away_price=-105),
            _row("Caesars", 4.5, -4.5, away_price=-112),
        ],
    }
    board = mod.build_decision_board_state_v2([_game()], payload, {"verification": "VERIFIED", "features": []}, {"verification": "UNAVAILABLE", "observations": []}, now_utc=NOW)
    market = board["games"][0]["market_intelligence"]
    assert market["sportsbook_count"] == 4
    assert market["consensus_away_spread"] == 4.5
    assert market["best_away"]["sportsbook"] == "FanDuel"
    assert market["best_home"]["spread"] == -4.0
    assert len(market["quotes"]) == 4
    assert market["movement"]["kind"] == "OPEN_TO_CURRENT"
    assert market["movement"]["open_away_spread"] == 3.5
    assert market["movement"]["current_away_spread"] == 4.5


def test_page_v9_is_additive_and_renders_real_analytics_hierarchy_without_duplicate_cta():
    mod = _module("nba_spread_page_v9")
    assert mod.FROZEN_PARENT_PAGE == "nba_spread_page_v8"
    assert mod.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert mod.MAY_MODIFY_MODEL is False
    assert mod.MAY_MODIFY_PROJECTION is False
    assert mod.MAY_MODIFY_PROBABILITY is False
    assert mod.MAY_MODIFY_RANKING is False
    record = {
        **_game(), "date": "2026-10-20", "away_logo": None, "home_logo": None,
        "market": {"verification": "VERIFIED", "away_spread": 4.5, "home_spread": -4.5, "label": "4 books verified"},
        "fair": {"verification": "VERIFIED", "away_spread": 2.1, "home_spread": -2.1},
        "cover": {"verification": "VERIFIED", "away_probability": 0.61, "home_probability": 0.39},
        "edge_points": 2.4,
        "injuries": {"away_summary": "PHI: 3 OUT • 3 Q", "home_summary": "NYK: clear"},
        "decision": {"verification": "VERIFIED", "decision_state": "PLAY", "pick_text": "PHI +4.5", "pick_strength": "STRONG", "production_grade": "A"},
        "market_intelligence": {
            "verification": "VERIFIED", "sportsbook_count": 4, "consensus_away_spread": 4.5, "consensus_home_spread": -4.5,
            "best_away": {"sportsbook": "FanDuel", "spread": 4.5, "price": -108}, "best_home": {"sportsbook": "BetMGM", "spread": -4.0, "price": -110},
            "quotes": [
                {"sportsbook": "FanDuel", "away_spread": 4.5, "home_spread": -4.5, "away_price": -108, "home_price": -112},
                {"sportsbook": "DraftKings", "away_spread": 4.5, "home_spread": -4.5, "away_price": -110, "home_price": -110},
                {"sportsbook": "BetMGM", "away_spread": 4.0, "home_spread": -4.0, "away_price": -105, "home_price": -115},
                {"sportsbook": "Caesars", "away_spread": 4.5, "home_spread": -4.5, "away_price": -112, "home_price": -108},
            ],
            "movement": {"verification": "VERIFIED", "kind": "OPEN_TO_CURRENT", "open_away_spread": 3.5, "current_away_spread": 4.5, "label": "PHI +3.5 → +4.5"},
        },
    }
    html = mod._decision_card_html(record)
    for expected in ("61.0%", "COVER PROBABILITY", "MARKET CONSENSUS", "KYRE FAIR LINE", "LINE VALUE", "FanDuel", "DraftKings", "BetMGM", "Caesars", "PHI +3.5", "PHI +4.5", "KYRE AI VERDICT", "STRONG", "PHI: 3 OUT", "NYK: clear"):
        assert expected in html
    assert "View Full Analysis" not in html


def test_isolated_runtime_overlay_advances_nba_only_and_can_inherit_a_future_base_loader():
    loader = _module("universal_runtime_v5_loader_nba_spread_stier_v2")
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    loader_source = (ROOT / "universal_runtime_v5_loader_nba_spread_stier_v2.py").read_text(encoding="utf-8")
    assert "nba_spread_page_v9" in loader_source
    assert "universal_runtime_v5_loader_v25" in loader_source
    assert "universal_runtime_v5_loader_v24" in loader_source
    assert loader.BASE_LOADER_NAME in {"universal_runtime_v5_loader_v24", "universal_runtime_v5_loader_v25"}
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v8" in source
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v7" not in source
    assert "NBA SPREAD PAGE1 S-TIER V2" in loader.MODEL_VERSION
