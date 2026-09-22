from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _games() -> list[dict]:
    return [
        {
            "event_id": "1",
            "date": "2026-08-29",
            "opponent": "Opponent A",
            "location": "home",
            "result": "W",
            "score": "31-14",
            "opponent_record_pct": 0.600,
        },
        {
            "event_id": "2",
            "date": "2026-09-05",
            "opponent": "Opponent B",
            "location": "away",
            "result": "L",
            "score": "20-24",
            "opponent_record_pct": 0.500,
        },
    ]


def test_evidence_state_exposes_visible_summary_and_completed_games() -> None:
    from cfb_game_total_clean_page_v5 import _team_evidence_state

    profile = {
        "team": "Syracuse",
        "data_source": "ESPN exact-event/current-season reconciliation",
        "completed_games": _games(),
    }
    state = _team_evidence_state(profile, {"away_team": "Syracuse"}, "away")

    assert state["team"] == "Syracuse"
    assert state["record"] == "1-1"
    assert state["ppg"] == 25.5
    assert state["allowed_pg"] == 19.0
    assert state["point_diff_pg"] == 6.5
    assert state["recent_form"] == "WL"
    assert state["data_source"] == "ESPN exact-event/current-season reconciliation"
    assert len(state["completed_games"]) == 2


def test_evidence_center_contract_has_independent_team_expanders() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v5.py").read_text(encoding="utf-8")

    assert "def _render_evidence_center" in source
    assert 'f"{away_team} evidence"' in source
    assert 'f"{home_team} evidence"' in source
    assert "expanded=False" in source
    assert "Recent completed games" in source
    assert "DATA SOURCE" in source
    assert "SOS" in source
    assert "Split context" in source


def test_evidence_center_precedes_model_gate_and_deep_audit() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v5.py").read_text(encoding="utf-8")

    evidence = source.index("_render_evidence_center(")
    model_gate = source.index("_status_cards(", evidence)
    deep_audit = source.index('st.expander("📊 Deep model evidence', model_gate)

    assert evidence < model_gate < deep_audit


def test_v5_keeps_frozen_model_and_sportsbook_boundaries() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v5.py").read_text(encoding="utf-8")

    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v4"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "selected_result = frozen_page.slate.analyze_game(game, selected_day)" in source
    assert "runtime_display.reconcile_display_bundle(" in source
