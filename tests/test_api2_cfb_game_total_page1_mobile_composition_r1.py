from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "cfb_game_total_page1_atier_v1.py"
V2 = ROOT / "cfb_game_total_page1_atier_v2.py"
WRAPPER = ROOT / "cfb_game_total_page1_api_bootstrap_repair_r1.py"
APP = ROOT / "app.py"


def test_successor_exists_and_live_wrapper_activates_it_without_app_mutation():
    assert V2.exists(), "STATIC_PROOF: compact mobile successor not implemented"
    wrapper = WRAPPER.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "import cfb_game_total_page1_atier_v2 as atier" in wrapper
    assert "return atier.render_game_total_page1()" in wrapper
    assert "cfb_game_total_page1_atier_v2" not in app


def test_mobile_card_is_one_compact_three_metric_decision_row():
    assert V2.exists(), "STATIC_PROOF: compact mobile successor not implemented"
    source = V2.read_text(encoding="utf-8")
    assert "cfbgt2-marketrow" in source
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in source.replace(" ", "")
    assert "cfbgt2-total" in source
    assert "cfbgt2-over" in source
    assert "cfbgt2-under" in source
    assert "cfbgt2-probbar" in source
    assert "cfbgt2-probfill" in source
    assert "NO-VIG MARKET" in source
    assert "MARKET READ" in source
    assert "OPEN ANALYSIS" in source
    assert ".cfbgt2-cell.primary{grid-column:1/-1}" not in source


def test_successor_preserves_kyre_api_only_and_safe_market_math_contract():
    assert V2.exists(), "STATIC_PROOF: compact mobile successor not implemented"
    source = V2.read_text(encoding="utf-8")
    lowered = source.casefold()
    assert 'PAGE1_ENDPOINT = "/api/v1/cfb/game-total/page1"' in source
    assert "cfb_game_total_page1_api_bootstrap_repair_r1" in source
    assert "sgo" not in lowered
    assert "espn" not in lowered
    assert "espn bet" not in lowered
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_RANKING = False" in source
    assert "target=\"_self\"" in source
    for provider in ("FanDuel", "DraftKings", "BetMGM", "Caesars", "bet365", "Fanatics"):
        assert provider not in source


def test_old_mobile_root_cause_is_documented_and_v1_remains_immutable_baseline():
    old = V1.read_text(encoding="utf-8")
    assert ".cfbgt1-cell.primary{grid-column:1/-1}" in old
    assert "cfbgt1-grid" in old
