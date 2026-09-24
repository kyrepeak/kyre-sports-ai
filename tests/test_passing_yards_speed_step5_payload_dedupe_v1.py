from __future__ import annotations

import re

import nfl_passing_yards_hub_v63 as v63
import nfl_passing_yards_hub_v64 as v64
import nfl_passing_yards_hub_v65 as v65
import nfl_passing_yards_hub_v66 as v66
import nfl_passing_yards_hub_v67 as v67
import nfl_passing_yards_hub_v81 as v81
import streamlit_memory_lazy_router_v232 as v232


def _captured(size: int = 20000) -> dict[str, list[str]]:
    return {
        "identity": ["IDENTITY", "I2"],
        "market": ["MARKET", "M2"],
        "projection": ["PROJECTION", "P2"],
        "context": ["CONTEXT", "C2"],
        "distribution": ["DISTRIBUTION", "D2"],
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
    assert v81.PARSER_GUARD_VERSION == "bounded-b-v1"
    assert v81.MAX_DETAIL_VALUE_CHARS == 240
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


def test_speed_step5_bounded_span_cannot_cross_prior_bold_tags():
    junk = "J" * 5000
    source = (
        "<div><b>PREFIX</b>" + junk +
        '<div><b>274.5</b><span>Market Line</span></div></div>'
    )
    old = v63._extract_b_span(source, "Market Line")
    new = v81._bounded_b_span(source, "Market Line")
    assert len(old) > 5000
    assert new == "274.5"


def test_speed_step5_bounded_label_cannot_cross_prior_bold_tags():
    junk = "K" * 5000
    source = (
        "<div><b>PREFIX</b>" + junk +
        "<div><b>52% / 48%</b>Model Over / Under</div></div>"
    )
    old = v63._extract_b_label(source, "Model Over / Under")
    new = v81._bounded_b_label(source, "Model Over / Under")
    assert len(old) > 5000
    assert new == "52% / 48%"


def test_speed_step5_compact_panel_does_not_reembed_raw_payload():
    captured = _captured()
    old = v67.build_deep_evidence(captured, 1)
    new = v81.build_compact_deep_evidence(captured, 1)

    assert "PROFILE_SENTINEL_" in old
    assert "DEFENSE_SENTINEL_" in old
    assert "PROFILE_SENTINEL_" not in new
    assert "DEFENSE_SENTINEL_" not in new
    assert 'data-passing-yards-payload-dedupe="v81"' in new
    assert 'data-passing-yards-bounded-detail-parser="v81"' in new

    match = re.search(r'data-step5-avoided-duplicate-bytes="(\d+)"', new)
    assert match is not None
    assert int(match.group(1)) >= 100000
    assert len(new.encode("utf-8")) < len(old.encode("utf-8")) // 10


def test_speed_step5_render_installs_and_restores_all_guards(monkeypatch):
    originals = {
        "v63_span": v63._extract_b_span,
        "v63_label": v63._extract_b_label,
        "v64_span": v64._extract_b_span,
        "v64_label": v64._extract_b_label,
        "v65_span": v65._extract_b_span,
        "v65_label": v65._extract_b_label,
        "v66_span": v66._extract_b_span,
        "deep": v67.build_deep_evidence,
    }
    seen = {"during": False, "markdown": False}

    def fake_markdown(*args, **kwargs):
        seen["markdown"] = True

    def fake_render():
        seen["during"] = all((
            v63._extract_b_span is v81._bounded_b_span,
            v63._extract_b_label is v81._bounded_b_label,
            v64._extract_b_span is v81._bounded_b_span,
            v64._extract_b_label is v81._bounded_b_label,
            v65._extract_b_span is v81._bounded_b_span,
            v65._extract_b_label is v81._bounded_b_label,
            v66._extract_b_span is v81._bounded_b_span,
            v67.build_deep_evidence is v81.build_compact_deep_evidence,
        ))
        return "rendered"

    monkeypatch.setattr(v81.st, "markdown", fake_markdown)
    monkeypatch.setattr(v81.prior, "render_nfl_passing_yards_hub", fake_render)

    assert v81.render_nfl_passing_yards_hub() == "rendered"
    assert seen == {"during": True, "markdown": True}
    assert v63._extract_b_span is originals["v63_span"]
    assert v63._extract_b_label is originals["v63_label"]
    assert v64._extract_b_span is originals["v64_span"]
    assert v64._extract_b_label is originals["v64_label"]
    assert v65._extract_b_span is originals["v65_span"]
    assert v65._extract_b_label is originals["v65_label"]
    assert v66._extract_b_span is originals["v66_span"]
    assert v67.build_deep_evidence is originals["deep"]


def test_speed_step5_router_advances_only_passing_yards():
    assert v232.FROZEN_ROUTER == "streamlit_memory_lazy_router_v231"
    assert v232.PASSING_HUB == "nfl_passing_yards_hub_v81"
    assert v232.FALLBACK_HUB == "nfl_passing_yards_hub_v80"
    assert v232.PAYLOAD_DEDUPE_VERSION == "v81"
    assert v232.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
