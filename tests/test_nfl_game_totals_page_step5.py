from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nfl_game_totals_hub_v5.py"
CONTEXT = ROOT / "sports_api" / "nfl_game_totals_explosive_context_v1.py"
ROUTER = ROOT / "nfl_hub_v18.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_context_module():
    spec = importlib.util.spec_from_file_location("step5_context", CONTEXT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_step5_runtime_files_exist_and_build_state_advances():
    assert PAGE.exists(), "Step 5 page module has not been implemented yet"
    assert CONTEXT.exists(), "Step 5 explosive-context module has not been implemented yet"
    source = _read(PAGE)
    assert 'MODEL_VERSION = "NFL GAME TOTALS V5' in source
    assert "PAGE_BUILD_STEP = 5" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "EXPLOSIVE_SCORING_ENABLED = True" in source
    assert "PACE_POSSESSION_ENABLED = True" in source
    assert "OFFENSE_DEFENSE_ENABLED = True" in source
    assert "LIVE_MARKET_ENABLED = True" in source
    assert "PROJECTION_MODEL_ENABLED = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STEP 5 OF 10" in source
    assert '("1", "VERIFIED SLATE", True)' in source
    assert '("2", "LIVE TOTAL", True)' in source
    assert '("3", "OFFENSE VS DEFENSE", True)' in source
    assert '("4", "PACE + POSSESSION", True)' in source
    assert '("5", "EXPLOSIVE SCORING", True)' in source


def test_step5_uses_only_source_proven_espn_explosive_fields_and_games_denominator():
    source = _read(CONTEXT)
    assert "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/statistics" in source
    assert 'RUSHING_BIG_PLAYS = "rushingBigPlays"' in source
    assert 'RECEIVING_BIG_PLAYS = "receivingBigPlays"' in source
    assert 'GAMES_PLAYED = "gamesPlayed"' in source
    assert "totalOffensivePlays" not in source
    assert "sportsbook_projection_weight" in source
    assert "descriptive_only" in source


def test_step5_extracts_explosive_rates_from_exact_espn_fields():
    module = _load_context_module()
    payload = {
        "results": {
            "stats": {
                "categories": [
                    {"name": "rushing", "stats": [
                        {"name": "rushingBigPlays", "value": 8},
                    ]},
                    {"name": "receiving", "stats": [
                        {"name": "receivingBigPlays", "value": 6},
                    ]},
                    {"name": "general", "stats": [
                        {"name": "gamesPlayed", "value": 4},
                    ]},
                ]
            }
        }
    }
    metrics = module.extract_explosive_metrics(payload)
    assert metrics["ready"] is True
    assert metrics["games_played"] == 4.0
    assert metrics["rushing_big_plays"] == 8.0
    assert metrics["receiving_big_plays"] == 6.0
    assert metrics["total_big_plays"] == 14.0
    assert metrics["rushing_big_plays_per_game"] == 2.0
    assert metrics["receiving_big_plays_per_game"] == 1.5
    assert metrics["explosive_plays_per_game"] == 3.5


def test_step5_explosive_labels_are_simple_and_deterministic():
    module = _load_context_module()
    assert module.classify_explosive_scoring(4.5) == "HIGH"
    assert module.classify_explosive_scoring(3.0) == "BALANCED"
    assert module.classify_explosive_scoring(1.5) == "LOW"


def test_step5_same_matchup_card_grows_downward_from_v4():
    source = _read(PAGE)
    assert "import nfl_game_totals_hub_v4 as v4" in source
    assert "v4._game_card(row, snapshot, scoring_context, pace_context)" in source
    assert "💥 EXPLOSIVE SCORING • STEP 5" in source
    assert "20+ RUSH/G" in source
    assert "20+ RECEIVE/G" in source
    assert "EXPLOSIVE PLAYS/G" in source
    assert "HIGH" in source
    assert "BALANCED" in source
    assert "LOW" in source
    assert "descriptive only" in source.lower()


def test_step5_preserves_steps_2_through_4_and_projection_firewall():
    source = _read(PAGE)
    assert "v4.v3.v2._market_snapshots(games)" in source
    assert "v4.v3._matchup_contexts(games, day_str)" in source
    assert "v4._pace_contexts(games, day_str)" in source
    assert "FanDuel" in source
    assert "projection remains OFF" in source
    assert "sportsbook influence stays 0.0%" in source


def test_existing_nfl_router_advances_only_game_total_to_v5():
    source = _read(ROUTER)
    assert 'if market == "Game Total":' in source
    assert "from nfl_game_totals_hub_v5 import render_nfl_game_totals_hub" in source
    assert "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub" in source
    assert "return base.render_nfl_hub(market)" in source
