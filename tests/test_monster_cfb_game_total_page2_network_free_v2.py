from pathlib import Path
import pytest

import cfb_game_total_page2_network_free_v2 as bridge

ROOT = Path(__file__).resolve().parents[1]


def _payload():
    return {
        "away": {
            "team": "Memphis",
            "recent_points_allowed_pg": 22.4,
            "official_stats": {
                "plays_per_game": {"value": 72.0, "source": "verified"},
                "yards_per_play": {"value": 6.1, "source": "verified"},
                "red_zone": {"display_value": "8-10", "source": "verified"},
            },
            "completed_games": [{"score": "40-17"}],
        },
        "home": {
            "team": "Tulane",
            "recent_points_allowed_pg": 19.8,
            "official_stats": {
                "plays_per_game": {"value": 68.0, "source": "verified"},
                "yards_per_play": {"value": 5.7, "source": "verified"},
                "red_zone": {"display_value": "7-9", "source": "verified"},
            },
            "completed_games": [{"score": "31-24"}],
        },
        "raw": {},
        "final": {"projected_total": 51.5, "market_line": 54.5},
    }


def test_preloaded_bridge_fills_screenshot_cards_and_preserves_model_truth():
    payload = _payload()
    out = bridge.enrich_preloaded_payload(payload)
    assert out["away"]["plays_per_game"] == 72.0
    assert out["home"]["plays_per_game"] == 68.0
    assert out["away"]["yards_per_play"] == 6.1
    assert out["home"]["yards_per_play"] == 5.7
    assert out["away"]["red_zone_rate"] == pytest.approx(0.8)
    assert out["home"]["red_zone_rate"] == pytest.approx(7 / 9)
    assert out["away"]["points_allowed_pg"] == 22.4
    assert out["home"]["points_allowed_pg"] == 19.8
    assert out["away"]["completed_games"][0]["points_for"] == 40.0
    assert out["away"]["completed_games"][0]["points_against"] == 17.0
    assert out["final"] == payload["final"]


def test_active_bridge_has_no_provider_fetch_path(monkeypatch):
    calls = []

    def blocked(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("provider HTTP must not run from Page 2")

    monkeypatch.setattr(bridge.prior.step3_owner.runtime_snapshot_v2.requests, "get", blocked)
    monkeypatch.setattr(bridge.prior.pace_owner.requests, "get", blocked)
    bridge.enrich_preloaded_payload(_payload())
    assert calls == []
    source = (ROOT / "cfb_game_total_page2_network_free_v2.py").read_text()
    assert "_fetch_sportsdataverse_game(" not in source
    assert "build_step5_contract(" not in source
    assert "build_step6_contract(" not in source
    assert "_runtime_v2_step3_bundle(" not in source


def test_same_page_shell_activates_v2_and_current_router_preserves_cfb_delegate():
    shell = (ROOT / "cfb_game_total_page2_same_page_shell_repair_v1.py").read_text()
    active = (ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py").read_text()
    frozen = (ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1.py").read_text()
    assert "import cfb_game_total_page2_network_free_v2 as live_data" in shell
    assert "with live_data.install_page2_live_data_repair():" in shell
    assert "import streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1 as prior" in active
    assert "return prior.render_app()" in active
    assert 'SAME_PAGE_RUNTIME = "cfb_game_total_page2_same_page_shell_repair_v1"' in frozen
    assert "return page.render_selected_in_shared_shell()" in frozen
