from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE1 = ROOT / "nba_pra_page1_v2.py"
PAGE2 = ROOT / "nba_pra_page2_v1.py"
RUNTIME = ROOT / "nba_pra_runtime_v2.py"


def _item() -> dict:
    return {
        "key": "andrewnembhard",
        "player_name": "Andrew Nembhard",
        "team": "IND",
        "position": "PG",
        "featured_quote": {
            "sportsbook": "FanDuel",
            "line": 23.5,
            "over_price": -106,
            "under_price": -125,
            "observed_at_utc": "2026-10-21T18:57:55Z",
        },
        "model": {"projection": 27.9, "sigma": 6.0, "basis": "VERIFIED HISTORY"},
        "grade": {
            "line": 23.5,
            "edge": 4.4,
            "over_probability": 0.768,
            "under_probability": 0.232,
            "lean": "OVER",
            "confidence": "HIGH",
            "score": 8.2,
            "tier": "STRONG",
        },
    }


def test_selection_handoff_preserves_exact_page1_analysis_and_quote() -> None:
    from nba_pra_runtime_v2 import (
        SESSION_ANALYSIS_HANDOFF,
        SESSION_NAV_PHASE,
        SESSION_PLAYER,
        SESSION_SELECTED_QUOTE,
        select_player_for_analysis,
    )

    state: dict = {}
    select_player_for_analysis(state, _item())

    assert state[SESSION_PLAYER] == "andrewnembhard"
    assert state[SESSION_SELECTED_QUOTE] == _item()["featured_quote"]
    assert state[SESSION_ANALYSIS_HANDOFF]["model"] == _item()["model"]
    assert state[SESSION_ANALYSIS_HANDOFF]["grade"] == _item()["grade"]
    assert state[SESSION_ANALYSIS_HANDOFF]["player_key"] == "andrewnembhard"
    assert state[SESSION_NAV_PHASE] == "loading_page2"


def test_page2_uses_page1_handoff_for_initial_book_line_parity() -> None:
    from nba_pra_page2_v1 import resolve_initial_analysis

    profile = {
        "current_games": [
            {"points": 12, "rebounds": 2, "assists": 8, "minutes": 31},
            {"points": 15, "rebounds": 3, "assists": 9, "minutes": 33},
        ],
        "prior_games": [],
    }
    handoff = {"player_key": "andrewnembhard", "model": _item()["model"], "grade": _item()["grade"], "quote": _item()["featured_quote"]}
    model, result = resolve_initial_analysis(profile, handoff, "andrewnembhard", 23.5)

    assert model == _item()["model"]
    assert result == _item()["grade"]
    assert result["over_probability"] == _item()["grade"]["over_probability"]
    assert result["edge"] == _item()["grade"]["edge"]


def test_page2_does_not_reuse_handoff_for_a_different_player_or_line() -> None:
    from nba_pra_page2_v1 import resolve_initial_analysis

    profile = {
        "current_games": [
            {"points": 12, "rebounds": 2, "assists": 8, "minutes": 31},
            {"points": 15, "rebounds": 3, "assists": 9, "minutes": 33},
        ],
        "prior_games": [],
    }
    handoff = {"player_key": "andrewnembhard", "model": _item()["model"], "grade": _item()["grade"], "quote": _item()["featured_quote"]}
    model, result = resolve_initial_analysis(profile, handoff, "otherplayer", 23.5)

    assert model != _item()["model"] or result != _item()["grade"]


def test_every_page1_market_player_has_analyze_player_action() -> None:
    source = PAGE1.read_text(encoding="utf-8")
    assert 'f"Analyze {item[\'player_name\']} →"' in source
    assert "View {item['player_name']} on Page 2" not in source
    assert "select_player_for_analysis" in source


def test_runtime_has_dedicated_page2_loading_phase_without_rendering_page1_behind_it() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    assert "loading_page2" in source
    assert "render_page2_loading_screen" in source
    loading_block = source.split('if nav_phase == "loading_page2"', 1)[1].split("player_key =", 1)[0]
    assert "render_nba_pra_page1_v2" not in loading_block


def test_active_sync_path_has_no_sgo_or_espn() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in (PAGE1, PAGE2, RUNTIME)
    )
    assert "sportsgameodds" not in combined
    assert "espn bet" not in combined
    assert "espn" not in combined
