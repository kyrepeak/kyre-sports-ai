# V165 CI trigger checkpoint — no behavior change
from __future__ import annotations

from pathlib import Path

import cfb_game_total_step4_matchup_v2 as step4

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v16.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v161.py"
APP = ROOT / "app.py"


def _identity(away="Miami (FL)", home="Wake Forest"):
    return {
        "away": {"team": away, "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/2390.png"},
        "home": {"team": home, "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/154.png"},
    }


def _away():
    return {
        "team": "Miami (FL)",
        "success_rate": 48.2,
        "success_rate_allowed": 36.4,
        "epa_per_play": 0.22,
        "epa_allowed_per_play": -0.06,
        "havoc_allowed_rate": 9.4,
        "havoc_rate": 18.1,
    }


def _home():
    return {
        "team": "Wake Forest",
        "success_rate": 41.5,
        "success_rate_allowed": 44.3,
        "epa_per_play": 0.08,
        "epa_allowed_per_play": 0.11,
        "havoc_allowed_rate": 15.8,
        "havoc_rate": 12.2,
    }


def _dim(edge, off_rank, def_rank, off_value, def_value):
    return {
        "ready": True,
        "edge": edge,
        "offense_rank": off_rank,
        "defense_rank": def_rank,
        "offense_value": off_value,
        "defense_value": def_value,
    }


def _fake_engine():
    return {
        "ready": True,
        "model_ready": True,
        "away_offense": {
            "dimensions": {
                "passing": _dim(0.24, 22, 55, "292.0", "231.0"),
                "rushing": _dim(0.11, 31, 46, "181.0", "152.0"),
                "third_down": _dim(0.15, 28, 51, "48.2%", "39.4%"),
                "red_zone": _dim(0.10, 34, 49, "91.7%", "78.6%"),
                "sack_pressure": _dim(-0.09, 78, 66, "4", "7"),
                "turnovers": _dim(0.07, 41, 52, "2", "4"),
            }
        },
        "home_offense": {
            "dimensions": {
                "passing": _dim(-0.21, 74, 45, "212.0", "198.0"),
                "rushing": _dim(0.05, 47, 54, "159.0", "149.0"),
                "third_down": _dim(-0.12, 73, 55, "32.1%", "36.8%"),
                "red_zone": _dim(-0.09, 69, 56, "72.7%", "80.0%"),
                "sack_pressure": _dim(-0.18, 83, 59, "6", "8"),
                "turnovers": _dim(-0.10, 70, 55, "5", "3"),
            }
        },
    }


def test_v165_step4_is_presentation_only_and_zero_market_influence():
    assert step4.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step4.MAY_MODIFY_PROJECTION is False
    assert step4.FROZEN_PREDECESSOR == "cfb_game_total_step4_matchup_v1"


def test_v165_step4_builds_six_tile_matchup_cards_from_verified_inputs():
    contract = step4.build_step4_contract(
        _identity(),
        _away(),
        _home(),
        engine=_fake_engine(),
    )
    assert contract["state"] == "READY"
    assert contract["verified_tiles"] == 12
    away = contract["away_offense_vs_home_defense"]
    home = contract["home_offense_vs_away_defense"]
    assert [tile["label"] for tile in away["tiles"]] == [
        "Pass Yds/G",
        "Rush Yds/G",
        "3rd Down",
        "Red Zone",
        "Sack Matchup",
        "Turnover Pressure",
    ]
    assert away["read_title"] == "Slight offensive edge"
    assert home["read_title"] in {"Slight defensive edge", "Tough offensive matchup"}
    assert away["impact"].startswith("↑") or away["impact"].startswith("↔")


def test_v165_step4_keeps_unverified_advanced_metrics_blank():
    sparse_away = {"team": "Miami (FL)"}
    sparse_home = {"team": "Wake Forest"}
    contract = step4.build_step4_contract(
        _identity(),
        sparse_away,
        sparse_home,
        engine=_fake_engine(),
    )
    away = contract["away_offense_vs_home_defense"]
    labels = {tile["label"] for tile in away["tiles"]}
    assert "Success Rate" not in labels
    assert "EPA / Play" not in labels
    assert "Havoc" not in labels
    assert "Success Rate" in contract["advanced_missing"]
    assert "EPA / Play" in contract["advanced_missing"]
    assert "Havoc" in contract["advanced_missing"]


def test_v165_step4_renders_open_fun_board_and_vertical_stack():
    html = step4.render_step4_html(
        "CHECK",
        _identity(),
        _away(),
        _home(),
        engine=_fake_engine(),
    )
    assert 'data-testid="gt157-step-4"' in html
    assert 'data-testid="gt165-step4-away-off-home-def"' in html
    assert 'data-testid="gt165-step4-home-off-away-def"' in html
    assert "BIGGEST EDGE" in html
    assert "BIGGEST RISK" in html
    assert "O/U IMPACT" in html
    assert "Pass Yds/G" in html
    assert "Rush Yds/G" in html
    assert "3rd Down" in html
    assert "Red Zone" in html
    assert "Sack Matchup" in html
    assert "Turnover Pressure" in html
    assert "Pass Eff." not in html
    assert "gt165-logowrap" in html
    assert html.split(">", 1)[0].endswith(" open")
    assert ".gt159-stepgrid{grid-template-columns:1fr!important" in step4.STEP4_CSS


def test_v165_step4_is_universal_not_miami_wake_hardcoded():
    identity = _identity("Oregon", "Penn State")
    away = dict(_away(), team="Oregon")
    home = dict(_home(), team="Penn State")
    html = step4.render_step4_html(
        "CHECK",
        identity,
        away,
        home,
        engine=_fake_engine(),
    )
    assert "Oregon Offense" in html
    assert "Penn State Defense" in html
    assert "Miami (FL) Offense" not in html


def test_v165_page_advances_only_step4_owner():
    source = PAGE.read_text()
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v15"' in source
    assert "import cfb_game_total_step4_matchup_v2 as step4_owner" in source
    assert "prior_v164.step4_owner = step4_owner" in source
    assert "prior_v164.render_game_total_hub" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v165_router_advances_only_exact_game_total_page():
    source = ROUTER.read_text()
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v160"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v16"' in source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V165_STEP4_MATCHUP_ACTIVE"' in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_activates_v161_and_keeps_v160_source_compatibility():
    source = APP.read_text()
    assert "from streamlit_memory_lazy_router_v161 import record_bootstrap_import_ms, render_app" in source
    assert "from streamlit_memory_lazy_router_v160 import record_bootstrap_import_ms, render_app" in source


def test_v165_production_render_calls_verified_matchup_engine_without_model_mutation(monkeypatch):
    calls = []

    def fake_build(game, away, home):
        calls.append({
            "game": dict(game or {}),
            "away": dict(away or {}),
            "home": dict(home or {}),
        })
        return _fake_engine()

    monkeypatch.setattr(
        step4.matchup_engine,
        "build_matchup_engine",
        fake_build,
    )

    html = step4.render_step4_html(
        "CHECK",
        _identity(),
        _away(),
        _home(),
    )

    assert len(calls) == 1
    assert calls[0]["away"]["team"] == "Miami (FL)"
    assert calls[0]["home"]["team"] == "Wake Forest"
    assert "Miami (FL) Offense" in html
    assert "Wake Forest Offense" in html
    assert "Projection mutation: OFF" in html
    assert "sportsbook influence: 0.0%" in html
    assert step4.MAY_MODIFY_PROJECTION is False
    assert step4.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_v165_step4_does_not_overstate_sparse_ranked_evidence():
    sparse_engine = _fake_engine()
    sparse_engine["away_offense"]["dimensions"] = {
        "passing": _dim(0.02, 44, 47, "250.0", "245.0"),
    }
    contract = step4.build_step4_contract(
        _identity(),
        {"team": "Miami (FL)"},
        {"team": "Wake Forest"},
        engine=sparse_engine,
    )
    away = contract["away_offense_vs_home_defense"]
    assert away["read_title"] == "Verified matchup data limited"
    assert away["biggest_edge"] == "Verified edge data limited"
    assert away["biggest_risk"] == "Verified edge data limited"
    assert away["impact"] == "↔ Scoring impact unclear"


def _fallback_dim(off_value, def_value):
    return {
        "ready": True,
        "edge": None,
        "offense_rank": None,
        "defense_rank": None,
        "offense_value": off_value,
        "defense_value": def_value,
        "source": "cfbstats.com",
        "display_fallback": True,
    }


def _fake_fallback():
    return {
        "ready": True,
        "source": "cfbstats.com",
        "away_offense": {
            "dimensions": {
                "passing": _fallback_dim("427.0", "242.5"),
                "rushing": _fallback_dim("275.5", "137.5"),
                "third_down": _fallback_dim("64.3%", "48.2%"),
                "red_zone": _fallback_dim("80.0%", "100.0%"),
                "sack_pressure": _fallback_dim("0.00/g", "2.50/g"),
                "turnovers": _fallback_dim("1.00/g", "0.50/g"),
            }
        },
        "home_offense": {
            "dimensions": {
                "passing": _fallback_dim("290.5", "145.5"),
                "rushing": _fallback_dim("194.5", "57.5"),
                "third_down": _fallback_dim("46.2%", "20.7%"),
                "red_zone": _fallback_dim("90.0%", "100.0%"),
                "sack_pressure": _fallback_dim("1.00/g", "1.50/g"),
                "turnovers": _fallback_dim("0.00/g", "0.00/g"),
            }
        },
    }


def test_v165_step4_multisource_fallback_fills_only_ncaa_missing_tiles():
    sparse = _fake_engine()
    sparse["away_offense"]["dimensions"]["red_zone"]["ready"] = False
    sparse["away_offense"]["dimensions"]["sack_pressure"]["ready"] = False
    sparse["away_offense"]["dimensions"]["turnovers"]["ready"] = False
    sparse["home_offense"]["dimensions"]["rushing"]["ready"] = False
    sparse["home_offense"]["dimensions"]["third_down"]["ready"] = False
    sparse["home_offense"]["dimensions"]["red_zone"]["ready"] = False
    sparse["home_offense"]["dimensions"]["sack_pressure"]["ready"] = False
    sparse["home_offense"]["dimensions"]["turnovers"]["ready"] = False

    original_passing_edge = sparse["away_offense"]["dimensions"]["passing"]["edge"]
    contract = step4.build_step4_contract(
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-18"},
        engine=sparse,
        fallback=_fake_fallback(),
    )

    assert contract["state"] == "READY"
    assert contract["verified_tiles"] == 12
    assert contract["coverage"] == 1.0
    assert contract["fallback_source"] == "cfbstats.com"
    assert contract["fallback_filled"] == 8

    away = {
        tile["label"]: tile
        for tile in contract["away_offense_vs_home_defense"]["tiles"]
    }
    home = {
        tile["label"]: tile
        for tile in contract["home_offense_vs_away_defense"]["tiles"]
    }
    assert away["Pass Yds/G"]["edge"] == original_passing_edge
    assert away["Red Zone"]["grade"] == "DATA"
    assert away["Sack Matchup"]["detail"] == "OFF 0.00/g • DEF 2.50/g"
    assert home["Rush Yds/G"]["detail"] == "OFF 194.5 • DEF 57.5"
    assert home["3rd Down"]["detail"] == "OFF 46.2% • DEF 20.7%"


def test_v165_step4_ready_requires_all_twelve_visible_tiles():
    sparse = _fake_engine()
    sparse["home_offense"]["dimensions"]["turnovers"]["ready"] = False
    contract = step4.build_step4_contract(
        _identity(),
        _away(),
        _home(),
        engine=sparse,
    )
    assert contract["verified_tiles"] == 11
    assert contract["state"] == "CHECK"
    assert contract["ready"] is False


def test_v165_step4_render_exposes_100_percent_multisource_proof():
    sparse = _fake_engine()
    for side in ("away_offense", "home_offense"):
        for key in ("red_zone", "sack_pressure", "turnovers"):
            sparse[side]["dimensions"][key]["ready"] = False

    html = step4.render_step4_html(
        "CHECK",
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-18"},
        engine=sparse,
        fallback=_fake_fallback(),
    )
    assert 'data-step4-state="READY"' in html
    assert 'data-step4-coverage="100"' in html
    assert "cfbstats fallback recovered" in html
    assert "Visible matchup coverage: 100%." in html
