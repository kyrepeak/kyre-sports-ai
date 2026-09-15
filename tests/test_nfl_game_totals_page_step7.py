from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nfl_game_totals_hub_v7.py"
CONTEXT = ROOT / "sports_api" / "nfl_game_totals_environment_context_v1.py"
ROUTER = ROOT / "nfl_hub_v18.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_context_module():
    spec = importlib.util.spec_from_file_location("step7_context", CONTEXT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_step7_runtime_files_exist_and_build_state_advances():
    assert PAGE.exists(), "Step 7 page module has not been implemented yet"
    assert CONTEXT.exists(), "Step 7 environment-context module has not been implemented yet"
    source = _read(PAGE)
    assert 'MODEL_VERSION = "NFL GAME TOTALS V7' in source
    assert "PAGE_BUILD_STEP = 7" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "GAME_ENVIRONMENT_ENABLED = True" in source
    assert "RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED = True" in source
    assert "EXPLOSIVE_SCORING_ENABLED = True" in source
    assert "PACE_POSSESSION_ENABLED = True" in source
    assert "OFFENSE_DEFENSE_ENABLED = True" in source
    assert "LIVE_MARKET_ENABLED = True" in source
    assert "PROJECTION_MODEL_ENABLED = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STEP 7 OF 10" in source
    for stage in (
        '("1", "VERIFIED SLATE", True)',
        '("2", "LIVE TOTAL", True)',
        '("3", "OFFENSE VS DEFENSE", True)',
        '("4", "PACE + POSSESSION", True)',
        '("5", "EXPLOSIVE SCORING", True)',
        '("6", "RED ZONE + DRIVES", True)',
        '("7", "GAME ENVIRONMENT", True)',
    ):
        assert stage in source


def test_step7_uses_only_source_proven_espn_environment_fields():
    source = _read(CONTEXT)
    assert "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard" in source
    assert "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary" in source
    assert 'VENUE_INDOOR_FIELD = "indoor"' in source
    assert 'WEATHER_FIELDS = ("temperature", "precipitation", "gust")' in source
    assert "sportsbook_projection_weight" in source
    assert "descriptive_only" in source


def test_step7_indoor_weather_is_neutralized_even_when_summary_has_weather():
    module = _load_context_module()
    event = {"id": "1", "competitions": [{"venue": {"fullName": "Indoor Dome", "indoor": True}}]}
    summary = {"gameInfo": {"weather": {"temperature": 99, "precipitation": 95, "gust": 40}}}
    metrics = module.extract_environment_metrics(event, summary)
    assert metrics["ready"] is True
    assert metrics["venue_name"] == "Indoor Dome"
    assert metrics["indoor"] is True
    assert metrics["weather_applies"] is False
    assert metrics["weather_pressure"] == "INDOOR"


def test_step7_outdoor_weather_extracts_exact_fields():
    module = _load_context_module()
    event = {"id": "2", "competitions": [{"venue": {"fullName": "Outdoor Field", "indoor": False}}]}
    summary = {"gameInfo": {"weather": {"temperature": 64, "precipitation": 20, "gust": 15, "conditionId": "7"}}}
    metrics = module.extract_environment_metrics(event, summary)
    assert metrics["ready"] is True
    assert metrics["venue_name"] == "Outdoor Field"
    assert metrics["indoor"] is False
    assert metrics["weather_applies"] is True
    assert metrics["temperature"] == 64.0
    assert metrics["precipitation"] == 20.0
    assert metrics["gust"] == 15.0
    assert metrics["weather_pressure"] == "WATCH"


def test_step7_weather_pressure_is_simple_and_deterministic():
    module = _load_context_module()
    assert module.classify_weather_pressure(85, 9, 9, indoor=False) == "LOW"
    assert module.classify_weather_pressure(64, 20, 15, indoor=False) == "WATCH"
    assert module.classify_weather_pressure(62, 63, 5, indoor=False) == "HIGH"
    assert module.classify_weather_pressure(20, 100, 50, indoor=True) == "INDOOR"


def test_step7_same_matchup_card_grows_downward_from_v6():
    source = _read(PAGE)
    assert "import nfl_game_totals_hub_v6 as v6" in source
    assert "v6._game_card(row, snapshot, scoring_context, pace_context, explosive_context, red_zone_drive_context)" in source
    assert "🌦️ GAME ENVIRONMENT • STEP 7" in source
    assert "VENUE TYPE" in source
    assert "TEMP" in source
    assert "PRECIP" in source
    assert "GUST" in source
    assert "LOW" in source
    assert "WATCH" in source
    assert "HIGH" in source
    assert "WEATHER NEUTRALIZED" in source
    assert "descriptive only" in source.lower()


def test_step7_preserves_steps_2_through_6_and_projection_firewall():
    source = _read(PAGE)
    assert "v6.v5.v4.v3.v2._market_snapshots(games)" in source
    assert "v6.v5.v4.v3._matchup_contexts(games, day_str)" in source
    assert "v6.v5.v4._pace_contexts(games, day_str)" in source
    assert "v6.v5._explosive_contexts(games, day_str)" in source
    assert "v6._red_zone_drive_contexts(games, day_str)" in source
    assert "FanDuel" in source
    assert "projection remains off" in source.lower()
    assert "sportsbook influence stays 0.0%" in source


def test_existing_nfl_router_advances_only_game_total_to_v7():
    source = _read(ROUTER)
    assert 'if market == "Game Total":' in source
    assert "from nfl_game_totals_hub_v7 import render_nfl_game_totals_hub" in source
    assert "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub" in source
    assert "return base.render_nfl_hub(market)" in source
