from __future__ import annotations

from pathlib import Path

import cfb_game_total_clean_page_v15 as page_v164
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



def test_v164_uses_kyre_api_exact_ids_before_direct_espn_fallback(monkeypatch):
    game = {
        "espn_event_id": "401869940",
        "game_date": "2026-09-19",
        "away_team": "Coastal Carolina",
        "home_team": "Delaware",
    }
    monkeypatch.setattr(
        logo_identity,
        "_api_rows",
        lambda _day: (
            {
                "event_id": "401869940",
                "away_team_id": "324",
                "home_team_id": "48",
            },
        ),
    )
    monkeypatch.setattr(
        logo_identity,
        "_espn_rows",
        lambda _day: (_ for _ in ()).throw(AssertionError("direct ESPN fallback should not run")),
    )
    enriched = logo_identity.enrich_exact_team_ids(game, {"games": []})
    assert enriched["away_espn_team_id"] == "324"
    assert enriched["home_espn_team_id"] == "48"


def test_v164_team_identity_endpoint_is_additive_and_projection_neutral():
    source = _read(ROOT / "cfb_game_total_team_logo_identity_v1.py")
    assert 'TEAM_IDENTITY_ENDPOINT = "/api/v1/cfb/identity/team-logos"' in source
    assert "_api_rows" in source
    assert "projection_weight" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source

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


def test_v164_display_reconcile_enriches_exact_team_ids_before_frozen_logo_resolution(monkeypatch):
    def frozen_reconcile(game, selected_day, frozen_away, frozen_home):
        return (
            {
                "espn_event_id": "401869940",
                "game_date": "2026-09-19",
                "away_team": "Coastal Carolina",
                "home_team": "Delaware",
            },
            dict(frozen_away),
            dict(frozen_home),
            {"runtime_status": "GREEN"},
        )

    monkeypatch.setattr(
        page_v164,
        "_FROZEN_RECONCILE_DISPLAY_BUNDLE",
        frozen_reconcile,
    )
    monkeypatch.setattr(
        page_v164,
        "_selector_payload_for_day",
        lambda selected_day: {
            "games": [
                {
                    "event_id": "401869940",
                    "away_team_id": "324",
                    "home_team_id": "48",
                    "identity_verified": True,
                }
            ]
        },
    )

    display_game, away, home, diag = page_v164._reconcile_display_bundle_v164(
        {"espn_event_id": "401869940"},
        "2026-09-19",
        {"team": "Coastal Carolina"},
        {"team": "Delaware"},
    )
    assert display_game["away_espn_team_id"] == "324"
    assert display_game["home_espn_team_id"] == "48"
    assert diag["v164_logo_team_ids_enriched"] is True

    visuals = frozen_logo.resolve_visuals(display_game)
    assert visuals["away"]["logo"].endswith("/324.png")
    assert visuals["home"]["logo"].endswith("/48.png")


def test_v164_visible_header_identity_receives_exact_logo_fields(monkeypatch):
    monkeypatch.setattr(
        page_v164.logo_identity,
        "_game_date",
        lambda _game: "2026-09-19",
    )
    monkeypatch.setattr(
        page_v164,
        "_selector_payload_for_day",
        lambda _day: {"games": []},
    )
    monkeypatch.setattr(
        page_v164.logo_identity,
        "enrich_exact_team_ids",
        lambda game, _payload: {
            **dict(game),
            "away_espn_team_id": "324",
            "home_espn_team_id": "48",
        },
    )
    monkeypatch.setattr(
        page_v164,
        "_FROZEN_RESOLVE_VISUALS",
        lambda _game: {
            "away": {
                "team_id": "324",
                "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/324.png",
                "exact_identity": True,
            },
            "home": {
                "team_id": "48",
                "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/48.png",
                "exact_identity": True,
            },
        },
    )

    identity = {
        "away": {"team": "Coastal Carolina", "logo": "", "exact_identity": False},
        "home": {"team": "Delaware", "logo": "", "exact_identity": False},
    }
    enriched = page_v164._identity_with_v164_logos(
        identity,
        {"espn_event_id": "401869940", "game_date": "2026-09-19"},
    )
    assert enriched["away"]["team_id"] == "324"
    assert enriched["home"]["team_id"] == "48"
    assert enriched["away"]["logo"].endswith("/324.png")
    assert enriched["home"]["logo"].endswith("/48.png")
    assert enriched["away"]["exact_identity"] is True
    assert enriched["home"]["exact_identity"] is True


def test_v164_render_patches_the_actual_v10_visible_matchup_owner():
    source = _read(PAGE)
    assert "target_owner = prior_v163.v161.prior_v160" in source
    assert "target_owner._target_matchup_header_html = target_matchup_wrapper" in source
    assert "identity.clear()" in source
    assert "identity.update(enriched_identity)" in source
