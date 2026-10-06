from __future__ import annotations

import json

from devsystem import nfl_live_game_repair_step5_final_cert_v1 as cert


def test_step5_scope_is_final_proof_only():
    assert cert.MISSION_STEP == "5/5"
    assert cert.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert cert.MAY_MODIFY_ROUTER is False
    assert cert.MAY_MODIFY_PROJECTION is False
    assert cert.MAY_MODIFY_PROBABILITY is False
    assert cert.MAY_MODIFY_RANKING is False
    assert cert.MAY_MODIFY_SPORTSBOOK is False
    assert cert.API2_USED is False


def test_step5_repository_contract_pins_frozen_runtime():
    proof = cert.verify_repository_contract()
    assert proof["status"] == "GREEN"
    assert proof["rushing_frozen_exact"] is True
    assert proof["receiving_frozen_exact"] is True
    assert proof["shared_gate_frozen_exact"] is True
    assert proof["router_owners_exact"] is True
    assert proof["production_target_canonical"] is True


def test_step5_uses_single_canonical_production_target():
    targets = json.loads(cert.PRODUCTION_TARGETS_PATH.read_text(encoding="utf-8"))
    expected = targets["streamlit"]["url"].rstrip("/")
    assert cert.production_base_url() == expected
    assert cert.production_base_url() == "https://pickvault.streamlit.app"
    assert cert.production_base_url() != cert.LEGACY_STREAMLIT_HOST


def test_step5_pregame_live_final_lifecycle_is_green():
    lifecycle = cert.certify_synthetic_lifecycle()
    assert lifecycle["status"] == "GREEN"
    for page in ("rushing", "receiving"):
        assert lifecycle[page]["pregame_pending"]["ready"] is True
        assert lifecycle[page]["pregame_confirmed"]["ready"] is True
        assert lifecycle[page]["live"]["ready"] is True
        assert lifecycle[page]["live"]["identity_state"] == "LIVE"
        assert lifecycle[page]["live"]["prop_market_open"] is False
        assert lifecycle[page]["final"]["ready"] is False
        assert lifecycle[page]["final"]["fail_closed"] is True


def test_step5_responsive_contract_uses_fresh_browser_per_viewport():
    assert cert.RESPONSIVE_VIEWPORTS == ((390, 844), (768, 1024), (1440, 1000))
    assert cert.FRESH_BROWSER_PER_VIEWPORT is True
    assert cert.PUBLIC_ROUTES == (("NFL", "Rushing Yards"), ("NFL", "Receiving Yards"))


def test_step5_live_retry_clears_cached_transport_failure(monkeypatch):
    import nfl_rushing_yards_hub_v16 as page

    state = {"cleared": False, "calls": 0}

    class CachedTransport:
        def clear(self) -> None:
            state["cleared"] = True

    def loader(event_id: str) -> dict:
        state["calls"] += 1
        if not state["cleared"]:
            return {
                "ready": False,
                "data_available": False,
                "reason": "Kyre Sports API request failed: ReadTimeout",
            }
        return {
            "ready": True,
            "data_available": True,
            "reason": "",
            "step7_app_identity_verified": True,
            "step7_app_identity_state": "LIVE",
            "step7_app_live_identity_verified": True,
            "step7_app_final_inactives_verified": False,
            "market_enabled": False,
            "sportsbook_influence": 0.0,
            "step3_live_roster_filtered_count": 0,
            "teams": [
                {
                    "players": [
                        {
                            "official_athlete_id": "1",
                            "step7_app_identity_verified": True,
                        }
                    ]
                },
                {"players": []},
            ],
        }

    monkeypatch.setattr(page, "_load_rushing_context_step7", loader)
    monkeypatch.setattr(page, "_ORIGINAL_LOAD", CachedTransport())
    monkeypatch.setattr(cert.time, "sleep", lambda _seconds: None)

    proof = cert._current_live_page(
        event_id="401000001",
        market="Rushing Yards",
        attempts=2,
    )

    assert proof["status"] == "GREEN"
    assert state["calls"] == 2
    assert state["cleared"] is True
