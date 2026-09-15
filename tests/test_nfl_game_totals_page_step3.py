from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nfl_game_totals_hub_v3.py"
CONTEXT = ROOT / "sports_api" / "nfl_game_totals_scoring_context_v1.py"
ROUTER = ROOT / "nfl_hub_v18.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_step3_runtime_files_exist_and_build_state_advances():
    assert PAGE.exists(), "Step 3 page module has not been implemented yet"
    assert CONTEXT.exists(), "Step 3 scoring-context module has not been implemented yet"
    source = _read(PAGE)
    assert 'MODEL_VERSION = "NFL GAME TOTALS V3' in source
    assert "PAGE_BUILD_STEP = 3" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "OFFENSE_DEFENSE_ENABLED = True" in source
    assert "LIVE_MARKET_ENABLED = True" in source
    assert "PROJECTION_MODEL_ENABLED = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STEP 3 OF 10" in source
    assert '("1", "VERIFIED SLATE", True)' in source
    assert '("2", "LIVE TOTAL", True)' in source
    assert '("3", "OFFENSE VS DEFENSE", True)' in source


def test_step3_uses_independent_espn_team_scoring_context():
    assert CONTEXT.exists(), "Step 3 scoring-context module has not been implemented yet"
    source = _read(CONTEXT)
    assert "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/schedule" in source
    assert '"seasontype": 2' in source
    assert '"ppg"' in source
    assert '"papg"' in source
    assert "PRIOR_GAMES = 6.0" in source
    assert "LEAGUE_PPG_REF = 22.5" in source
    assert "sportsbook_projection_weight" in source
    assert "descriptive_only" in source


def test_step3_descriptive_signal_thresholds_are_simple_and_deterministic():
    assert CONTEXT.exists(), "Step 3 scoring-context module has not been implemented yet"
    import importlib.util

    spec = importlib.util.spec_from_file_location("step3_context", CONTEXT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.classify_scoring_matchup(26.0, 25.0) == "FAVORABLE"
    assert module.classify_scoring_matchup(22.5, 22.5) == "MEDIUM"
    assert module.classify_scoring_matchup(18.0, 20.0) == "TOUGH"


def test_step3_same_matchup_card_grows_downward_from_v2():
    source = _read(PAGE)
    assert "import nfl_game_totals_hub_v2 as v2" in source
    assert "v2._game_card(row, snapshot)" in source
    assert "⚔️ OFFENSE VS DEFENSE • STEP 3" in source
    assert "OFFENSE PF/G" in source
    assert "OPP DEFENSE PA/G" in source
    assert "FAVORABLE" in source
    assert "MEDIUM" in source
    assert "TOUGH" in source
    assert "descriptive only" in source.lower()


def test_step3_preserves_step2_market_and_projection_firewall():
    source = _read(PAGE)
    assert "v2._market_snapshots(games)" in source
    assert "FanDuel" in source
    assert "projection remains OFF" in source
    assert "sportsbook influence stays 0.0%" in source


def test_existing_nfl_router_advances_only_game_total_to_v3():
    source = _read(ROUTER)
    assert 'if market == "Game Total":' in source
    assert "from nfl_game_totals_hub_v3 import render_nfl_game_totals_hub" in source
    assert "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub" in source
    assert "return base.render_nfl_hub(market)" in source
