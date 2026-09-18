from __future__ import annotations

from pathlib import Path

import cfb_game_total_team_logo_identity_v1 as logo_identity
import cfb_over_under_logo_resolver_v3 as frozen_logo

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v15.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v160.py"
APP = ROOT / "app.py"


def _read(path: Path) -> str:
    assert path.exists(), f"missing required V164 file: {path.name}"
    return path.read_text(encoding="utf-8")


def test_v164_selector_payload_supplies_exact_espn_team_ids_without_name_guessing():
    game = {
        "espn_event_id": "401869940",
        "game_date": "2026-09-19",
        "away_team": "Coastal Carolina",
        "home_team": "Delaware",
    }
    payload = {
        "games": [
            {
                "event_id": "401869940",
                "away_team_id": "324",
                "home_team_id": "48",
                "away_team": "Coastal Carolina",
                "home_team": "Delaware",
            }
        ]
    }
    enriched = logo_identity.enrich_exact_team_ids(game, payload)
    assert enriched["away_espn_team_id"] == "324"
    assert enriched["home_espn_team_id"] == "48"
    assert enriched["logo_identity_source"] == "ESPN exact event_id -> exact team IDs"


def test_v164_exact_ids_resolve_to_official_espn_logo_cdn():
    game = {
        "away_espn_team_id": "324",
        "home_espn_team_id": "48",
    }
    visuals = frozen_logo.resolve_visuals(game)
    assert visuals["away"]["logo"].endswith("/324.png")
    assert visuals["home"]["logo"].endswith("/48.png")
    assert visuals["away"]["exact_identity"] is True
    assert visuals["home"]["exact_identity"] is True


def test_v164_fails_closed_without_exact_event_identity():
    game = {
        "game_date": "2026-09-19",
        "away_team": "Coastal Carolina",
        "home_team": "Delaware",
    }
    payload = {
        "games": [
            {
                "event_id": "different-event",
                "away_team_id": "324",
                "home_team_id": "48",
            }
        ]
    }
    enriched = logo_identity.enrich_exact_team_ids(game, payload)
    assert "away_espn_team_id" not in enriched
    assert "home_espn_team_id" not in enriched


def test_v164_page_is_additive_over_frozen_v163():
    source = _read(PAGE)
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v14"' in source
    assert "cfb_game_total_team_logo_identity_v1" in source
    assert "_FROZEN_RESOLVE_VISUALS" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v164_router_advances_only_game_total_page():
    source = _read(ROUTER)
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v159"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v15"' in source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V164_PRODUCTION_ACTIVE"' in source
    assert 'LEGACY_V163_HEARTBEAT = "CFB_GAME_TOTAL_V163_PRODUCTION_ACTIVE"' in source
    assert "return prior._render_cfb_game_total_v159(market)" in source
    assert "return prior.render_app()" in source


def test_app_activates_router_v160():
    source = _read(APP)
    assert "from streamlit_memory_lazy_router_v160 import record_bootstrap_import_ms, render_app" in source
