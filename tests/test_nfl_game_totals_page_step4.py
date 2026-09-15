from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nfl_game_totals_hub_v4.py"
CONTEXT = ROOT / "sports_api" / "nfl_game_totals_pace_context_v1.py"
ROUTER = ROOT / "nfl_hub_v18.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_context_module():
    spec = importlib.util.spec_from_file_location("step4_context", CONTEXT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_step4_runtime_files_exist_and_build_state_advances():
    assert PAGE.exists(), "Step 4 page module has not been implemented yet"
    assert CONTEXT.exists(), "Step 4 pace-context module has not been implemented yet"
    source = _read(PAGE)
    assert 'MODEL_VERSION = "NFL GAME TOTALS V4' in source
    assert "PAGE_BUILD_STEP = 4" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "PACE_POSSESSION_ENABLED = True" in source
    assert "OFFENSE_DEFENSE_ENABLED = True" in source
    assert "LIVE_MARKET_ENABLED = True" in source
    assert "PROJECTION_MODEL_ENABLED = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STEP 4 OF 10" in source
    assert '("1", "VERIFIED SLATE", True)' in source
    assert '("2", "LIVE TOTAL", True)' in source
    assert '("3", "OFFENSE VS DEFENSE", True)' in source
    assert '("4", "PACE + POSSESSION", True)' in source


def test_step4_uses_proven_espn_team_stats_fields_only():
    assert CONTEXT.exists(), "Step 4 pace-context module has not been implemented yet"
    source = _read(CONTEXT)
    assert "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/statistics" in source
    assert 'TOTAL_OFFENSIVE_PLAYS = "totalOffensivePlays"' in source
    assert 'POSSESSION_TIME_SECONDS = "possessionTimeSeconds"' in source
    assert "sportsbook_projection_weight" in source
    assert "descriptive_only" in source
    assert "projection" not in source.lower().replace("sportsbook_projection_weight", "") or "descriptive" in source.lower()


def test_step4_extracts_exact_proven_metrics_from_espn_results_schema():
    module = _load_context_module()
    payload = {
        "results": {
            "stats": {
                "categories": [
                    {
                        "name": "rushing",
                        "stats": [
                            {
                                "name": "totalOffensivePlays",
                                "value": 199,
                                "perGameValue": 66.3,
                            }
                        ],
                    },
                    {
                        "name": "miscellaneous",
                        "stats": [
                            {
                                "name": "possessionTimeSeconds",
                                "value": 5460,
                                "perGameValue": 1820.0,
                            }
                        ],
                    },
                ]
            }
        }
    }
    metrics = module.extract_pace_metrics(payload)
    assert metrics["plays_per_game"] == 66.3
    assert metrics["possession_seconds_per_game"] == 1820.0
    assert metrics["ready"] is True


def test_step4_opportunity_pace_labels_are_simple_and_deterministic():
    module = _load_context_module()
    assert module.classify_opportunity_pace(68.0) == "HIGH"
    assert module.classify_opportunity_pace(64.0) == "BALANCED"
    assert module.classify_opportunity_pace(60.0) == "LOW"
    assert module.format_possession_clock(1820) == "30:20"


def test_step4_same_matchup_card_grows_downward_from_v3():
    source = _read(PAGE)
    assert "import nfl_game_totals_hub_v3 as v3" in source
    assert "v3._game_card(row, snapshot, scoring_context)" in source
    assert "⏱️ PACE + POSSESSION • STEP 4" in source
    assert "PLAYS/G" in source
    assert "POSSESSION/G" in source
    assert "HIGH" in source
    assert "BALANCED" in source
    assert "LOW" in source
    assert "descriptive only" in source.lower()


def test_step4_preserves_steps_2_and_3_and_projection_firewall():
    source = _read(PAGE)
    assert "v3.v2._market_snapshots(games)" in source
    assert "v3._matchup_contexts(games, day_str)" in source
    assert "FanDuel" in source
    assert "projection remains OFF" in source
    assert "sportsbook influence stays 0.0%" in source


def test_existing_nfl_router_advances_only_game_total_to_v4():
    source = _read(ROUTER)
    assert 'if market == "Game Total":' in source
    assert "from nfl_game_totals_hub_v4 import render_nfl_game_totals_hub" in source
    assert "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub" in source
    assert "return base.render_nfl_hub(market)" in source
