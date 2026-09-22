"""Regression checks for the strict no-TOUGH visible Hits hotfix."""

import pytest

import mlb_hit_strict_no_tough_v1 as strict
import mlb_hit_hub_v1321 as hits


def _row(name, profile, step5_score=80.0):
    return {
        "player_name": name,
        "starter_id": 123,
        "starter_name": "Starter",
        "_step5": {
            "qualified": True,
            "step5_score": step5_score,
            "p_one_plus": 0.72,
            "starter_profile": profile,
        },
    }


def test_certified_step2_grade_matches_frozen_thresholds():
    hayden_like = {"era": 3.18, "whip": 1.16, "k_pct": 0.209}
    assert strict.certified_step2_starter_grade(hayden_like) == "TOUGH"
    assert strict.certified_step2_starter_grade({"era": 4.90, "whip": 1.35, "k_pct": .20}) == "FAVORABLE"
    assert strict.certified_step2_starter_grade({"era": 4.00, "whip": 1.25, "k_pct": .22}) == "NEUTRAL"


def test_any_single_tough_threshold_is_enough():
    assert strict.certified_step2_starter_grade({"era": 3.30}) == "TOUGH"
    assert strict.certified_step2_starter_grade({"whip": 1.10}) == "TOUGH"
    assert strict.certified_step2_starter_grade({"k_pct": 0.28}) == "TOUGH"


def test_strict_filter_removes_hayden_like_visible_pick(monkeypatch):
    rows = [
        _row("Luis", {"era": 3.18, "whip": 1.16, "k_pct": .209}, 88.0),
        _row("Better Spot", {"era": 4.65, "whip": 1.31, "k_pct": .20}, 82.0),
    ]
    monkeypatch.setattr(strict, "_FROZEN_STEP5_RANKER", lambda results, profile_lookup, limit=999: (list(results), {
        "step4_qualified_count": 2,
        "hard_tough_starters_excluded": 0,
        "finalists_evaluated": 12,
        "tough_excluded": 0,
        "probability_excluded": 0,
        "opportunity_excluded": 0,
    }))

    selected, meta = strict.strict_rank_results(rows, lambda sid, name="": {}, limit=5)

    assert [x["player_name"] for x in selected] == ["Better Spot"]
    assert meta["strict_tough_excluded"] == 1
    assert meta["backfilled_tough"] == 0


def test_data_limited_does_not_false_exclude(monkeypatch):
    rows = [_row("Unknown Starter Data", {}, 75.0)]
    monkeypatch.setattr(strict, "_FROZEN_STEP5_RANKER", lambda results, profile_lookup, limit=999: (list(results), {}))
    selected, _ = strict.strict_rank_results(rows, lambda sid, name="": {}, limit=5)
    assert len(selected) == 1
    assert selected[0]["_strict_no_tough"]["certified_step2_starter_grade"] == "DATA LIMITED"


def test_hotfix_does_not_change_probability_or_simulation_contract(monkeypatch):
    rows = [_row("A", {"era": 4.0, "whip": 1.25, "k_pct": .22})]
    monkeypatch.setattr(strict, "_FROZEN_STEP5_RANKER", lambda results, profile_lookup, limit=999: (list(results), {}))
    selected, meta = strict.strict_rank_results(rows, lambda sid, name="": {}, limit=5)
    assert selected
    assert meta["probability_impact"] is False
    assert meta["simulation_impact"] is False
    assert meta["candidate_pool_impact"] is False
    assert meta["calibration_history_impact"] is False
    assert meta["visible_selection_impact"] is True


def test_ui_wrapper_is_additive_over_frozen_step5():
    assert hits.UI_VERSION == "V13.21"
    assert hits._BASE_PICK_HTML is hits.prior._pick_html_v1320


def test_strict_strip_states_visible_grade_and_no_backfill(monkeypatch):
    frozen = '<div class="hit1317-card"><div class="hit1320-starter">starter</div></div>'
    monkeypatch.setattr(hits, "_BASE_PICK_HTML", lambda result, rank: frozen)
    result = {
        "_strict_no_tough": {
            "certified_step2_starter_grade": "NEUTRAL",
            "strict_no_tough_qualified": True,
            "strict_rank": 1,
        }
    }
    html = hits._pick_html_v1321(result, 1)
    assert "STRICT MATCHUP GATE" in html
    assert "STEP-2 STARTER GRADE • NEUTRAL" in html
    assert "TOUGH starter grades are excluded, never back-filled." in html


def test_board_summary_calls_out_tough_removal():
    html = hits._strict_board_summary({
        "visible_count": 4,
        "strict_visible_count": 4,
        "strict_tough_excluded": 1,
        "step4_qualified_count": 5,
        "hard_tough_starters_excluded": 0,
        "finalists_evaluated": 12,
        "tough_excluded": 0,
        "probability_excluded": 0,
        "opportunity_excluded": 0,
    })
    assert "1 Step-2 TOUGH starter pick(s) removed" in html
    assert "No TOUGH backfill" in html
