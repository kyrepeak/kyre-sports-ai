from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "sports_api/api/nfl_moneyline_page2_v1.py"
PAGE2 = ROOT / "nfl_moneyline_page2_war_room_v1.py"
V20 = ROOT / "nfl_moneyline_hub_v20.py"
LOADER = ROOT / "universal_runtime_v5_loader_v21.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _history_frame() -> pd.DataFrame:
    rows = []
    dates = ["2026-01-01", "2025-12-01", "2025-01-01", "2024-12-01", "2024-01-01", "2023-12-01"]
    scores = [(24, 20), (17, 28), (31, 27), (21, 20), (13, 30), (27, 24)]
    for idx, (day, (dal, phi)) in enumerate(zip(dates, scores)):
        if idx % 2 == 0:
            rows.append({"gameday": day, "away_team": "DAL", "home_team": "PHI", "away_score": dal, "home_score": phi})
        else:
            rows.append({"gameday": day, "away_team": "PHI", "home_team": "DAL", "away_score": phi, "home_score": dal})
    rows.append({"gameday": "2025-10-01", "away_team": "NYG", "home_team": "DAL", "away_score": 10, "home_score": 20})
    return pd.DataFrame(rows)


def test_page2_files_and_route_successor_exist():
    assert API.exists(), "Kyre Sports API Page 2 gateway is missing"
    assert PAGE2.exists(), "War Room renderer is missing"
    assert V20.exists(), "Moneyline V20 selected-game owner is missing"


def test_history_is_nflverse_only_display_context_with_last5_and_full_history():
    api = _load(API, "nfl_moneyline_page2_v1_test")
    source = API.read_text(encoding="utf-8").casefold()
    assert "espn" not in source
    assert "sgo" not in source
    assert api.MODEL_INFLUENCE == 0.0
    assert api.DISPLAY_ONLY is True

    out = api.normalize_matchup_history(_history_frame(), "DAL", "PHI", limit=5, full_limit=50)
    assert out["status"] == "READY"
    assert out["source"] == "nflverse"
    assert len(out["recent_meetings"]) == 5
    assert len(out["full_meetings"]) == 6
    assert out["recent_meetings"][0]["date"] == "2026-01-01"
    assert out["full_meetings"][-1]["date"] == "2023-12-01"
    assert out["games"] == 6
    assert out["average_margin"] is not None
    assert out["series_summary"]


def test_history_fails_closed_without_verified_meetings():
    api = _load(API, "nfl_moneyline_page2_v1_empty_test")
    out = api.normalize_matchup_history(_history_frame(), "BUF", "KC", limit=5, full_limit=50)
    assert out["status"] == "SEMANTIC_EMPTY"
    assert out["semantic_state"] == "NO_PREVIOUS_MEETINGS"
    assert out["recent_meetings"] == []
    assert out["full_meetings"] == []


def test_page2_context_preserves_frozen_probability_edge_and_grade():
    api = _load(API, "nfl_moneyline_page2_v1_context_test")
    edge = {
        "ready": True,
        "away": {"model_p": 0.36, "market_p": 0.43, "edge": -0.07, "ev": -0.10, "best_price": 146},
        "home": {"model_p": 0.64, "market_p": 0.57, "edge": 0.07, "ev": 0.08, "best_price": -160},
    }
    final = {"ready": True, "state": "QUALIFIED", "leader_side": "home", "leader_grade": {"grade": "QUALIFIED"}}
    mc = {"ready": True, "converged": True, "simulations": 5_000_000, "home_win_rate": 0.64, "away_win_rate": 0.36}
    snap = {"ready": True, "quality": "HIGH", "best_home": {"price": -160, "book": "Book A"}, "best_away": {"price": 146, "book": "Book B"}, "rows": []}
    game = {"game_id": "g1", "away_abbr": "DAL", "home_abbr": "PHI", "away_team": "Dallas Cowboys", "home_team": "Philadelphia Eagles"}

    out = api.build_page2_context(game=game, final=final, edge_out=edge, mc_out=mc, snap=snap, profiles={}, contexts={}, gameplans={}, history={"status": "SEMANTIC_EMPTY", "recent_meetings": [], "full_meetings": []})
    assert math.isclose(out["verdict"]["model_probability"], 0.64)
    assert math.isclose(out["verdict"]["market_probability"], 0.57)
    assert math.isclose(out["verdict"]["edge"], 0.07)
    assert out["verdict"]["state"] == "QUALIFIED"
    assert out["verdict"]["pick_side"] == "home"
    assert out["guardrails"]["sportsbook_model_influence"] == 0.0
    assert out["guardrails"]["stake_sizing_enabled"] is False


def test_war_room_source_contains_all_approved_sections_and_mobile_contract():
    source = PAGE2.read_text(encoding="utf-8")
    required = (
        "WHY KYRE LIKES THIS SIDE",
        "TEAM VS TEAM ADVANTAGE",
        "MATCHUP HISTORY",
        "VIEW FULL HISTORY",
        "EXPECTED GAME SCRIPT",
        "KEY PLAYER AVAILABILITY",
        "RECENT FORM & SITUATIONAL INTEL",
        "MARKET INTELLIGENCE",
        "5M SIMULATION LAB",
        "RISK / UPSET RADAR",
        "KYRE SPORTS AI FINAL VERDICT",
        'data-testid="nfl-moneyline-page2-war-room"',
        "@media(max-width:520px)",
    )
    for marker in required:
        assert marker in source, marker
    lowered = source.casefold()
    assert "requests.get" not in lowered
    assert "espn" not in lowered
    assert "sgo" not in lowered


def test_v20_adds_selected_game_navigation_and_delegates_page1_to_v19():
    source = V20.read_text(encoding="utf-8")
    assert "import nfl_moneyline_hub_v19 as prior" in source
    assert "nfl_moneyline_page2_war_room_v1" in source
    assert "VIEW FULL ANALYSIS" in source
    assert "view=analysis" in source
    assert "game=" in source
    assert "SPORTSBOOK_MODEL_INFLUENCE = 0.0" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source


def test_universal_loader_activates_v20_for_nfl_moneyline_only():
    source = LOADER.read_text(encoding="utf-8")
    assert 'route.sport_id == "nfl" and route.market_id == "moneyline"' in source
    assert '"nfl_moneyline_hub_v20"' in source
    assert '"nfl_moneyline_hub_v19"' not in source
