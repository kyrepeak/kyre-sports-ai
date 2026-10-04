from __future__ import annotations

import pytest

from devsystem import cfb_top_picks_repair_step4_detail_integrity_v1 as cert


def _row():
    return {
        "rank": 1,
        "event_id": "401234567",
        "away": "Away State",
        "home": "Home Tech",
        "market": "MONEYLINE",
        "pick": "Away State",
    }


def _detail():
    return {
        "ready": True,
        "event_id": "401234567",
        "away_espn_team_id": "101",
        "home_espn_team_id": "202",
        "history_status": cert.history_router.VERIFIED_HISTORY,
        "history_ready": True,
        "no_history_claim_allowed": False,
        "meetings": 4,
        "why": "The certified model ranks Away State highly using verified inputs only.",
        "benefit": "Historical benefit for Away State: it leads the verified matchup series 3-1.",
        "history_projection_weight": 0.0,
        "history_selection_weight": 0.0,
        "history_ranking_weight": 0.0,
        "sportsbook_projection_weight": 0.0,
    }


def test_step4_current_v9_detail_contract_accepts_three_visible_sections(monkeypatch):
    html = (
        '<details open data-expanded="true">'
        '<h4>Why This Pick</h4>'
        '<h4>Actual Matchup History</h4>'
        '<h4>Benefits</h4>'
        '<h4>Market-Aware Football Reasoning</h4>'
        '</details>'
    )
    monkeypatch.setattr(cert.page, "_detail_card", lambda row, detail: html)

    result = cert._validate_detail(_row(), _detail())

    assert result["rank"] == 1
    assert result["event_id"] == "401234567"
    assert result["history_status"] == cert.history_router.VERIFIED_HISTORY
    assert result["away_espn_team_id"] == "101"
    assert result["home_espn_team_id"] == "202"


def test_step4_fails_closed_when_required_visible_section_is_missing(monkeypatch):
    html = (
        '<details open data-expanded="true">'
        '<h4>Why This Pick</h4>'
        '<h4>Actual Matchup History</h4>'
        '<h4>Market-Aware Football Reasoning</h4>'
        '</details>'
    )
    monkeypatch.setattr(cert.page, "_detail_card", lambda row, detail: html)

    with pytest.raises(AssertionError, match="STEP4_SURFACE_TOKEN:1:Benefits"):
        cert._validate_detail(_row(), _detail())


def test_step4_fails_closed_on_nonzero_history_or_sportsbook_weight(monkeypatch):
    detail = _detail()
    detail["history_ranking_weight"] = 0.25
    monkeypatch.setattr(
        cert.page,
        "_detail_card",
        lambda row, detail: (
            '<details open data-expanded="true">'
            'Why This Pick Actual Matchup History Benefits Market-Aware Football Reasoning'
            '</details>'
        ),
    )

    with pytest.raises(AssertionError, match="STEP4_NONZERO_WEIGHT:1:history_ranking_weight"):
        cert._validate_detail(_row(), detail)


def test_step4_no_history_claim_requires_verified_source_exhaustion(monkeypatch):
    detail = _detail()
    detail["history_status"] = cert.history_router.VERIFIED_NO_HISTORY
    detail["history_ready"] = False
    detail["no_history_claim_allowed"] = False
    monkeypatch.setattr(cert.page, "_detail_card", lambda row, detail: "")

    with pytest.raises(AssertionError, match="STEP4_NO_HISTORY_CLAIM_NOT_VERIFIED:1"):
        cert._validate_detail(_row(), detail)


def test_step4_proof_module_is_read_only_and_preserves_prior_frozen_work():
    assert cert.MISSION_STEP == "4/5"
    assert cert.API2_USED is False
    assert cert.MAY_MODIFY_PROJECTION is False
    assert cert.MAY_MODIFY_PROBABILITY is False
    assert cert.MAY_MODIFY_RANKING is False
    assert cert.MAY_MODIFY_SELECTION is False
    assert cert.HISTORY_PROJECTION_WEIGHT == 0.0
    assert cert.HISTORY_SELECTION_WEIGHT == 0.0
    assert cert.HISTORY_RANKING_WEIGHT == 0.0
    assert cert.SPORTSBOOK_PROJECTION_WEIGHT == 0.0
    assert cert.REQUIRED_SECTIONS == (
        "Why This Pick",
        "Actual Matchup History",
        "Benefits",
    )
