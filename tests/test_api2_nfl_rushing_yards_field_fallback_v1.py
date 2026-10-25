from __future__ import annotations

from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_active_roster_availability_is_explicit_and_never_fabricates_injury_clearance():
    slate = import_module("sports_api.api.nfl_rushing_yards_slate_v1")
    state = slate.availability_state_for_active_roster()
    assert state["status"] == "ACTIVE_ROSTER_VERIFIED_INJURY_DESIGNATION_UNRESOLVED"
    assert state["display"] == "Active roster · injury designation not verified"
    assert state["roster_verified"] is True
    assert state["injury_designation"] is None
    assert state["injury_designation_verified"] is False
    assert state["missing_to_zero"] is False
    assert state["resolution_state"] == "NO_CONFIGURED_APPROVED_INJURY_PROVIDER"
    providers = {row["provider"]: row["state"] for row in state["provider_attempts"]}
    assert providers["Official NFL/team injury reports"] == "NOT_INTEGRATED_IN_CURRENT_DEPLOYMENT"
    assert providers["Sportradar"] == "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"
    assert providers["SportsDataIO"] == "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"
    assert providers["RotoWire"] == "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"


def test_postprocessor_preserves_verified_card_and_adds_field_level_fallback_audit():
    slate = import_module("sports_api.api.nfl_rushing_yards_slate_v1")
    payload = {
        "ready": True,
        "schema_version": slate.SCHEMA_VERSION,
        "service": "kyre-sports-api",
        "gateway": "Kyre Sports API",
        "running_backs": [
            {
                "player_id": "kyre:nfl:player:00-1",
                "game_id": "kyre:nfl:game:g1",
                "role": "RB1",
                "market": {"status": "MARKET_NOT_POSTED", "line": None},
                "detail": {
                    "availability": {"status": "DATA_UNAVAILABLE"},
                    "source_lineage": {"identity": "nflverse weekly roster"},
                },
            }
        ],
        "routing": {
            "application_gateway": "Kyre Sports API",
            "canonical_ids": True,
            "sportsbook_line_averaging": False,
            "missing_to_zero": False,
        },
    }
    out = slate._postprocess_payload(payload)
    card = out["running_backs"][0]
    availability = card["detail"]["availability"]
    assert availability["roster_verified"] is True
    assert availability["injury_designation"] is None
    assert "Unavailable" not in availability["display"]
    assert "N/A" not in availability["display"]
    assert out["routing"]["availability_field_policy"]["active_roster_is_not_injury_clearance"] is True
    assert out["routing"]["market_field_policy"]["book_specific_records"] is True
    assert out["routing"]["market_field_policy"]["sportsbook_line_averaging"] is False
    assert out["routing"]["market_field_policy"]["provider_order"] == ["FanDuel direct", "The Odds API"]
    assert out["routing"]["market_field_policy"]["fallback_query_mode"] == "FIELD_SPECIFIC_STOP_ON_SATISFIED"


def test_market_provider_audit_is_field_specific_and_does_not_claim_unconfigured_sources_were_used():
    slate = import_module("sports_api.api.nfl_rushing_yards_slate_v1")
    audit = {row["provider"]: row["state"] for row in slate.MARKET_PROVIDER_AUDIT}
    assert audit["OpticOdds"] == "APPROVED_FALLBACK_NOT_CONFIGURED"
    assert audit["The Odds API"] == "CONFIGURED_APPROVED_FALLBACK"
    assert audit["SportsDataIO"] == "APPROVED_FALLBACK_NOT_CONFIGURED"
    assert audit["Direct sportsbook"] == "ACTIVE_FIELD_SOURCE"


def test_overlay_production_path_has_no_prohibited_provider_tokens():
    source = (ROOT / "sports_api" / "api" / "nfl_rushing_yards_slate_v1" / "__init__.py").read_text(encoding="utf-8").upper()
    for token in ("SGO", "ESPN", "ESPN BET"):
        assert token not in source
