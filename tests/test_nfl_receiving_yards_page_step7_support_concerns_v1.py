from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_v7_isolated():
    fake_streamlit = types.ModuleType("streamlit")
    fake_streamlit.markdown = lambda *args, **kwargs: None

    fake_prior = types.ModuleType("nfl_receiving_yards_hub_v6")
    fake_prior._player_card_v6 = lambda player, team, opponent: "<article>V6</article>"
    fake_prior._advance_step6_copy = lambda body: body
    fake_prior.render_nfl_receiving_yards_hub = lambda: None

    fake_projection = types.ModuleType("nfl_receiving_yards_projection_v1")
    fake_projection.build_player_projection = lambda **kwargs: kwargs.get("player", {}).get(
        "projection_fixture", {"ready": False}
    )

    names = (
        "streamlit",
        "nfl_receiving_yards_hub_v6",
        "nfl_receiving_yards_projection_v1",
    )
    previous = {name: sys.modules.get(name) for name in names}
    sys.modules["streamlit"] = fake_streamlit
    sys.modules["nfl_receiving_yards_hub_v6"] = fake_prior
    sys.modules["nfl_receiving_yards_projection_v1"] = fake_projection
    try:
        spec = importlib.util.spec_from_file_location(
            "nfl_receiving_yards_hub_v7_isolated",
            ROOT / "nfl_receiving_yards_hub_v7.py",
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, prior in previous.items():
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior


def _green_projection() -> dict:
    return {
        "ready": True,
        "official_event_id": "401000001",
        "official_athlete_id": "10",
        "expected_receptions": 5.0,
        "expected_yards_per_reception": 11.3,
        "efficiency_coverage": 1.0,
        "coverage_grade": "GREEN",
        "coverage_basis": "verified workload sample contains 5 games",
        "workload_source": "verified receptions_per_game",
        "efficiency_components": [
            {
                "key": "player_yards_per_reception",
                "value": 12.0,
                "normalized_weight": 0.65,
            },
            {
                "key": "opponent_yards_per_reception_allowed",
                "value": 10.0,
                "normalized_weight": 0.35,
            },
        ],
        "sportsbook_influence": 0.0,
        "market_enabled": False,
    }


def test_v7_is_additive_over_frozen_v6_and_advances_to_70_percent():
    source = _source("nfl_receiving_yards_hub_v7.py")
    assert "import nfl_receiving_yards_hub_v6 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v6"' in source
    assert 'FROZEN_PROJECTION_ENGINE = "nfl_receiving_yards_projection_v1"' in source
    assert "PAGE_BUILD_STEP = 7" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "70%!important" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "prior._player_card_v6 = _player_card_v7" in source
    assert "prior._player_card_v6 = original_card" in source


def test_support_concern_rows_classify_frozen_projection_evidence():
    module = _load_v7_isolated()
    supports, concerns = module._support_concern_rows(_green_projection())
    assert any("5 expected receptions" in row for row in supports)
    assert any("all certified player + exact-opponent blend inputs" in row for row in supports)
    assert any("Evidence quality" in row and "5 games" in row for row in supports)
    assert any("Player efficiency input: 12 YPR vs 11.3 blended expected YPR" in row for row in supports)
    assert any("Opponent YPR-allowed input: 10 YPR vs 11.3 blended expected YPR" in row for row in concerns)


def test_non_green_evidence_grade_is_a_concern_not_a_betting_grade():
    module = _load_v7_isolated()
    row = _green_projection()
    row["coverage_grade"] = "WATCH"
    row["coverage_basis"] = "projection is usable but workload sample contains only 1 game(s)"
    supports, concerns = module._support_concern_rows(row)
    assert supports
    assert any("Evidence quality is WATCH" in item for item in concerns)
    html = module._support_concerns_html(row)
    assert "not a betting grade" in html
    assert "no sportsbook line/price used" in html
    assert "sportsbook projection influence 0.0%" in html


def test_step7_reuses_frozen_projection_engine_without_duplicating_math():
    source = _source("nfl_receiving_yards_hub_v7.py")
    assert "import nfl_receiving_yards_projection_v1 as projection_engine" in source
    assert "projection_engine.build_player_projection(" in source
    assert "weighted_blend(" not in source
    assert "EFFICIENCY_WEIGHTS" not in source
    assert "0.65" not in source
    assert "0.35" not in source
    assert "projection_yards =" not in source


def test_step7_classifier_has_no_market_or_price_input():
    source = _source("nfl_receiving_yards_hub_v7.py")
    assert "def _support_concern_rows(\n    projection_row" in source
    assert "market_row" not in source
    assert "sportsbook_line" not in source
    assert "market_price" not in source
    assert "projection_yards -" not in source
    assert "line - projection" not in source
    for forbidden in (
        "probability_enabled = True",
        "grading_enabled = True",
        "recommendation_enabled = True",
        "wager_actions = True",
        "stake_size",
        "kelly",
    ):
        assert forbidden not in source


def test_player_card_appends_explanation_only_for_ready_projection():
    module = _load_v7_isolated()
    projection = _green_projection()
    html = module._player_card_v7(
        {"official_event_id": "401000001", "projection_fixture": projection},
        {"official_team_id": "1"},
        {"official_team_id": "2"},
    )
    assert "<article>V6</article>" in html
    assert "Support vs Concern" in html
    assert "Concerns / Counterweights" in html

    withheld = module._player_card_v7(
        {"official_event_id": "401000001", "projection_fixture": {"ready": False}},
        {"official_team_id": "1"},
        {"official_team_id": "2"},
    )
    assert withheld == "<article>V6</article>"


def test_router_v118_advances_only_receiving_to_v7():
    source = _source("streamlit_memory_lazy_router_v118.py")
    assert "import streamlit_memory_lazy_router_v117 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v117"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v7"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_boots_v118_and_preserves_v117_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v118 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V117_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V117_NFL_RECEIVING_YARDS_STEP6_PROJECTION_RECIPE_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V118_NFL_RECEIVING_YARDS_STEP7_SUPPORT_CONCERNS_2026-09-13"' in source


def test_frozen_v6_projection_and_router_remain_step6_owners():
    v6 = _source("nfl_receiving_yards_hub_v6.py")
    projection = _source("nfl_receiving_yards_projection_v1.py")
    router_v117 = _source("streamlit_memory_lazy_router_v117.py")
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v5"' in v6
    assert "PAGE_BUILD_STEP = 6" in v6
    assert '"sportsbook_influence": 0.0' in projection
    assert '"market_enabled": False' in projection
    assert '"probability_enabled": False' in projection
    assert '"ev_enabled": False' in projection
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v6"' in router_v117
