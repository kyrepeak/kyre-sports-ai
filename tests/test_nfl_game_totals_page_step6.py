from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nfl_game_totals_hub_v6.py"
CONTEXT = ROOT / "sports_api" / "nfl_game_totals_red_zone_drive_context_v1.py"
ROUTER = ROOT / "nfl_hub_v18.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_context_module():
    spec = importlib.util.spec_from_file_location("step6_context", CONTEXT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_step6_runtime_files_exist_and_build_state_advances():
    assert PAGE.exists(), "Step 6 page module has not been implemented yet"
    assert CONTEXT.exists(), "Step 6 red-zone/drive context module has not been implemented yet"
    source = _read(PAGE)
    assert 'MODEL_VERSION = "NFL GAME TOTALS V6' in source
    assert "PAGE_BUILD_STEP = 6" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED = True" in source
    assert "EXPLOSIVE_SCORING_ENABLED = True" in source
    assert "PACE_POSSESSION_ENABLED = True" in source
    assert "OFFENSE_DEFENSE_ENABLED = True" in source
    assert "LIVE_MARKET_ENABLED = True" in source
    assert "PROJECTION_MODEL_ENABLED = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STEP 6 OF 10" in source
    for stage in (
        '("1", "VERIFIED SLATE", True)',
        '("2", "LIVE TOTAL", True)',
        '("3", "OFFENSE VS DEFENSE", True)',
        '("4", "PACE + POSSESSION", True)',
        '("5", "EXPLOSIVE SCORING", True)',
        '("6", "RED ZONE + DRIVES", True)',
    ):
        assert stage in source


def test_step6_uses_only_source_proven_espn_fields_and_gap_certifies_drives():
    source = _read(CONTEXT)
    assert "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/statistics" in source
    assert 'RED_ZONE_TOUCHDOWN_PCT = "redzoneTouchdownPct"' in source
    assert 'THIRD_DOWN_CONV_PCT = "thirdDownConvPct"' in source
    assert 'FIRST_DOWNS = "firstDowns"' in source
    assert "DRIVE_COUNT_FIELD_AVAILABLE = False" in source
    assert "sportsbook_projection_weight" in source
    assert "descriptive_only" in source


def test_step6_extracts_red_zone_and_sustainability_metrics_from_exact_fields():
    module = _load_context_module()
    payload = {
        "results": {
            "stats": {
                "categories": [
                    {"name": "miscellaneous", "stats": [
                        {"name": "redzoneTouchdownPct", "value": 62.5},
                        {"name": "thirdDownConvPct", "value": 44.0},
                        {"name": "firstDowns", "value": 88, "perGameValue": 22.0},
                    ]},
                ]
            }
        }
    }
    metrics = module.extract_red_zone_drive_metrics(payload)
    assert metrics["ready"] is True
    assert metrics["red_zone_td_pct"] == 62.5
    assert metrics["third_down_conv_pct"] == 44.0
    assert metrics["first_downs_per_game"] == 22.0
    assert metrics["drive_count_available"] is False


def test_step6_sustainability_labels_are_simple_and_deterministic():
    module = _load_context_module()
    assert module.classify_drive_sustainability(65.0, 48.0, 24.0) == "HIGH"
    assert module.classify_drive_sustainability(52.0, 40.0, 21.0) == "BALANCED"
    assert module.classify_drive_sustainability(40.0, 30.0, 17.0) == "LOW"


def test_step6_same_matchup_card_grows_downward_from_v5():
    source = _read(PAGE)
    assert "import nfl_game_totals_hub_v5 as v5" in source
    assert "v5._game_card(row, snapshot, scoring_context, pace_context, explosive_context)" in source
    assert "🔴 RED ZONE + DRIVE SUSTAINABILITY • STEP 6" in source
    assert "RZ TD %" in source
    assert "3RD DOWN %" in source
    assert "1ST DOWNS/G" in source
    assert "HIGH" in source
    assert "BALANCED" in source
    assert "LOW" in source
    assert "descriptive only" in source.lower()
    assert "drive count unavailable" in source.lower()


def test_step6_preserves_steps_2_through_5_and_projection_firewall():
    source = _read(PAGE)
    assert "v5.v4.v3.v2._market_snapshots(games)" in source
    assert "v5.v4.v3._matchup_contexts(games, day_str)" in source
    assert "v5.v4._pace_contexts(games, day_str)" in source
    assert "v5._explosive_contexts(games, day_str)" in source
    assert "FanDuel" in source
    assert "projection remains off" in source.lower()
    assert "sportsbook influence stays 0.0%" in source


def test_existing_nfl_router_advances_only_game_total_to_v6():
    source = _read(ROUTER)
    assert 'if market == "Game Total":' in source
    assert "from nfl_game_totals_hub_v6 import render_nfl_game_totals_hub" in source
    assert "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub" in source
    assert "return base.render_nfl_hub(market)" in source
