from __future__ import annotations

from pathlib import Path

import cfb_game_total_step4_matchup_v3 as step4

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v17.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v162.py"
APP = ROOT / "app.py"


def _identity():
    return {
        "away": {"team": "Miami (FL)", "logo": "away.png"},
        "home": {"team": "Wake Forest", "logo": "home.png"},
    }


def _team(name):
    return {"team": name}


def _fallback_dim(offense_value, defense_value):
    return {
        "ready": True,
        "edge": None,
        "offense_rank": None,
        "defense_rank": None,
        "offense_value": offense_value,
        "defense_value": defense_value,
        "source": "cfbstats.com",
        "display_fallback": True,
    }


def _fallback():
    away = {
        "passing": _fallback_dim("427.0", "242.5"),
        "rushing": _fallback_dim("275.5", "137.5"),
        "third_down": _fallback_dim("64.3%", "48.2%"),
        "red_zone": _fallback_dim("80.0%", "100.0%"),
        "sack_pressure": _fallback_dim("0.00/g", "2.50/g"),
        "turnovers": _fallback_dim("1.00/g", "0.50/g"),
    }
    home = {
        "passing": _fallback_dim("290.5", "145.5"),
        "rushing": _fallback_dim("194.5", "57.5"),
        "third_down": _fallback_dim("46.2%", "20.7%"),
        "red_zone": _fallback_dim("90.0%", "100.0%"),
        "sack_pressure": _fallback_dim("1.00/g", "1.50/g"),
        "turnovers": _fallback_dim("0.00/g", "0.00/g"),
    }
    return {
        "ready": True,
        "source": "cfbstats.com",
        "away_offense": {"dimensions": away},
        "home_offense": {"dimensions": home},
    }


def _sparse_engine():
    return {
        "ready": True,
        "model_ready": False,
        "away_offense": {"dimensions": {}},
        "home_offense": {"dimensions": {}},
    }


def test_v166_v3_is_fresh_presentation_only_owner():
    assert step4.FROZEN_PREDECESSOR == "cfb_game_total_step4_matchup_v2"
    assert step4.MAY_MODIFY_PROJECTION is False
    assert step4.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step4.STEP4_PRESENTATION_MARKER == "CFB_GAME_TOTAL_STEP4_MATCHUP_V3_MULTISOURCE_ACTIVE"
    assert step4.STEP4_DATA_MARKER == "CFB_GAME_TOTAL_STEP4_MULTISOURCE_V3_DATA_ACTIVE"


def test_v166_v3_loads_fallback_even_when_frozen_v15_passes_no_game(monkeypatch):
    calls = []

    def fake_fallback(game, away, home):
        calls.append((game, dict(away), dict(home)))
        return _fallback()

    monkeypatch.setattr(step4.multisource, "build_display_fallback", fake_fallback)

    html = step4.render_step4_html(
        "CHECK",
        _identity(),
        _team("Miami (FL)"),
        _team("Wake Forest"),
        engine=_sparse_engine(),
    )

    assert len(calls) == 1
    assert calls[0][0] is None
    assert 'data-step4-state="READY"' in html
    assert 'data-step4-coverage="100"' in html
    assert 'data-step4-fallback-filled="12"' in html
    assert "Visible matchup coverage: 100%." in html
    assert "cfbstats fallback recovered 12" in html
    assert "Projection mutation: OFF" in html
    assert "sportsbook influence: 0.0%" in html


def test_v166_page_v17_forces_fresh_v3_owner_over_frozen_v15():
    source = PAGE.read_text(encoding="utf-8")
    assert 'import cfb_game_total_clean_page_v15 as prior_v164' in source
    assert 'import cfb_game_total_step4_matchup_v3 as step4_owner' in source
    assert 'prior_v164.step4_owner = step4_owner' in source
    assert 'prior_v164.render_game_total_hub' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert 'MAY_MODIFY_PROJECTION = False' in source


def test_v166_router_v162_advances_only_exact_game_total_route():
    source = ROUTER.read_text(encoding="utf-8")
    assert 'import streamlit_memory_lazy_router_v161 as prior' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v161"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v17"' in source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V166_STEP4_MULTISOURCE_ACTIVE"' in source
    assert 'return prior.render_app()' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source


def test_v166_app_runtime_boots_v162_and_preserves_v161_source_compatibility():
    source = APP.read_text(encoding="utf-8")
    runtime = source.split("try:", 1)[1]
    assert 'from streamlit_memory_lazy_router_v162 import record_bootstrap_import_ms, render_app' in runtime
    assert 'from streamlit_memory_lazy_router_v161 import record_bootstrap_import_ms, render_app' in source
