from __future__ import annotations

import re

import nfl_passing_yards_hub_v67 as v67
import nfl_passing_yards_hub_v81 as v81
import streamlit_memory_lazy_router_v232 as v232


def _captured(size: int = 20000) -> dict[str, list[str]]:
    return {
        "profile": ["PROFILE_SENTINEL_" + "P" * size, "P2"],
        "defense": ["DEFENSE_SENTINEL_" + "D" * size, "D2"],
        "pressure": ["PRESSURE_SENTINEL_" + "R" * size, "R2"],
        "personnel": ["PERSONNEL_SENTINEL_" + "N" * size, "N2"],
        "environment": ["ENVIRONMENT_SENTINEL_" + "E" * size],
    }


def test_speed_step5_contract_is_presentation_only():
    assert v81.FROZEN_PRIOR == "nfl_passing_yards_hub_v80"
    assert v81.SPEED_PHASE_STEP == 5
    assert v81.PAYLOAD_DEDUPE_VERSION == "v81"
    assert v81.PRESENTATION_ONLY is True
    assert v81.MAY_MODIFY_PROJECTION is False
    assert v81.MAY_MODIFY_CONTEXT_MATH is False
    assert v81.MAY_MODIFY_PROBABILITY is False
    assert v81.MAY_MODIFY_MARKET_MATH is False
    assert v81.MAY_MODIFY_SPORTSBOOK_BEHAVIOR is False
    assert v81.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert v81.MAY_MODIFY_WIDGET_KEYS is False
    assert v81.MAY_MODIFY_NAVIGATION_STATE is False
    assert v81.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v81.STAKE_SIZING_ENABLED is False


def test_speed_step5_compact_panel_does_not_reembed_raw_payload():
    captured = _captured()
    old = v67.build_deep_evidence(captured, 1)
    new = v81.build_compact_deep_evidence(captured, 1)

    assert "PROFILE_SENTINEL_" in old
    assert "DEFENSE_SENTINEL_" in old
    assert "PROFILE_SENTINEL_" not in new
    assert "DEFENSE_SENTINEL_" not in new
    assert 'data-passing-yards-payload-dedupe="v81"' in new

    match = re.search(r'data-step5-avoided-duplicate-bytes="(\d+)"', new)
    assert match is not None
    assert int(match.group(1)) >= 100000
    assert len(new.encode("utf-8")) < len(old.encode("utf-8")) // 10


def test_speed_step5_render_installs_and_restores_dedupe(monkeypatch):
    original = v67.build_deep_evidence
    seen = {"during": False, "markdown": False}

    def fake_markdown(*args, **kwargs):
        seen["markdown"] = True

    def fake_render():
        seen["during"] = v67.build_deep_evidence is v81.build_compact_deep_evidence
        return "rendered"

    monkeypatch.setattr(v81.st, "markdown", fake_markdown)
    monkeypatch.setattr(v81.prior, "render_nfl_passing_yards_hub", fake_render)

    assert v81.render_nfl_passing_yards_hub() == "rendered"
    assert seen == {"during": True, "markdown": True}
    assert v67.build_deep_evidence is original


def test_speed_step5_router_advances_only_passing_yards():
    assert v232.FROZEN_ROUTER == "streamlit_memory_lazy_router_v231"
    assert v232.PASSING_HUB == "nfl_passing_yards_hub_v81"
    assert v232.FALLBACK_HUB == "nfl_passing_yards_hub_v80"
    assert v232.PAYLOAD_DEDUPE_VERSION == "v81"
    assert v232.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
