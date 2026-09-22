"""Regression checks for MLB Hits Step 4 favorable matchup gate + hit-spot ranking."""
from copy import deepcopy

import pytest

import mlb_hit_favorable_ranker_v1 as ranker
import mlb_hit_hub_v1319 as hits


def _row(
    name,
    *,
    p1=0.70,
    avg=0.280,
    starter=0.295,
    bullpen=0.285,
    ab=4.3,
    confirmed=True,
    confidence="HIGH",
    data=8,
):
    return {
        "player_name": name,
        "season_avg": avg,
        "starter_rate": starter,
        "bullpen_rate": bullpen,
        "expected_ab": ab,
        "lineup_confirmed": confirmed,
        "confidence": confidence,
        "data_score": data,
        "sim": {"p_one_plus": p1},
    }


def test_matchup_context_labels_favorable_neutral_and_tough():
    fav = ranker.matchup_context(_row("Fav", avg=.270, starter=.300, bullpen=.290))
    neutral = ranker.matchup_context(_row("Neutral", avg=.280, starter=.283, bullpen=.279))
    tough = ranker.matchup_context(_row("Tough", avg=.300, starter=.270, bullpen=.275))

    assert fav["matchup_label"] == "FAVORABLE"
    assert neutral["matchup_label"] == "NEUTRAL"
    assert tough["matchup_label"] == "TOUGH"


def test_tough_matchup_is_never_qualified_even_with_high_probability():
    out = ranker.hit_spot_score(
        _row("Star in ugly spot", p1=.82, avg=.310, starter=.270, bullpen=.275, ab=4.6)
    )
    assert out["matchup_label"] == "TOUGH"
    assert out["qualified"] is False
    assert "tough_matchup" in out["gate_failures"]


def test_probability_and_opportunity_gates_are_real():
    low_p = ranker.hit_spot_score(_row("Low P", p1=.58))
    low_ab = ranker.hit_spot_score(_row("Low AB", ab=3.6))

    assert low_p["qualified"] is False
    assert "probability_below_gate" in low_p["gate_failures"]
    assert low_ab["qualified"] is False
    assert "opportunity_below_gate" in low_ab["gate_failures"]


def test_visible_board_can_pull_raw_rank_six_into_qualified_top5():
    rows = [
        _row("Raw1 Tough", p1=.82, avg=.310, starter=.270, bullpen=.272),
        _row("Raw2", p1=.76, avg=.280, starter=.300, bullpen=.292),
        _row("Raw3", p1=.74, avg=.275, starter=.294, bullpen=.287),
        _row("Raw4", p1=.72, avg=.280, starter=.288, bullpen=.284),
        _row("Raw5", p1=.71, avg=.270, starter=.291, bullpen=.280),
        _row("Raw6 Favorable", p1=.70, avg=.260, starter=.300, bullpen=.290),
    ]

    selected, meta = ranker.rank_favorable_results(rows, limit=5)
    names = [x["player_name"] for x in selected]

    assert "Raw1 Tough" not in names
    assert "Raw6 Favorable" in names
    assert meta["tough_excluded"] == 1
    assert meta["backfilled_tough"] == 0
    assert len(selected) == 5


def test_board_shows_fewer_than_five_instead_of_backfilling_tough():
    rows = [
        _row("Good1", p1=.72, avg=.270, starter=.295, bullpen=.290),
        _row("Good2", p1=.69, avg=.280, starter=.292, bullpen=.289),
        _row("Tough1", p1=.80, avg=.310, starter=.270, bullpen=.270),
        _row("Tough2", p1=.79, avg=.305, starter=.268, bullpen=.272),
    ]
    selected, meta = ranker.rank_favorable_results(rows, limit=5)

    assert len(selected) == 2
    assert meta["visible_count"] == 2
    assert meta["tough_excluded"] == 2
    assert meta["backfilled_tough"] == 0


def test_step4_does_not_mutate_model_result_payload():
    row = _row("Immutable")
    before = deepcopy(row)
    scored = ranker.hit_spot_score(row)
    assert row == before
    assert scored["hit_spot_score"] >= 0


def test_ranker_declares_only_visible_selection_and_ranking_impact():
    selected, meta = ranker.rank_favorable_results([_row("A")], limit=5)
    assert selected
    assert meta["probability_impact"] is False
    assert meta["simulation_impact"] is False
    assert meta["candidate_pool_impact"] is False
    assert meta["calibration_history_impact"] is False
    assert meta["visible_selection_impact"] is True
    assert meta["visible_ranking_impact"] is True


def test_step4_wrapper_is_additive_over_frozen_step3():
    assert hits.UI_VERSION == "V13.19"
    assert hits._BASE_PICK_HTML is hits.prior._pick_html_v1318


def test_step4_strip_is_inserted_before_step3_profile(monkeypatch):
    frozen = (
        '<div class="hit1317-card">'
        '<div>hero</div>'
        '<div class="hit1318-profile">step3 profile</div>'
        '<details class="hit1317-deep"><summary>evidence</summary></details>'
        '</div>'
    )
    monkeypatch.setattr(hits, "_BASE_PICK_HTML", lambda result, rank: frozen)
    monkeypatch.setattr(
        hits.ranker,
        "hit_spot_score",
        lambda result: {
            "qualified": True,
            "matchup_label": "FAVORABLE",
            "hit_spot_score": 88.4,
            "matchup_edge": 0.018,
        },
    )

    html = hits._pick_html_v1319(_row("A"), 1)

    assert "STEP 4 • FAVORABLE HIT-SPOT GATE" in html
    assert "88.4/100" in html
    assert "FAVORABLE" in html
    assert html.index("hit1319-strip") < html.index("hit1318-profile")


def test_board_summary_explicitly_says_no_tough_backfill():
    html = hits._board_summary({
        "visible_count": 3,
        "finalists_evaluated": 12,
        "tough_excluded": 4,
        "probability_excluded": 2,
        "opportunity_excluded": 1,
    })
    assert "ONLY 3 QUALIFIED" in html
    assert "No tough-matchup backfill" in html
    assert "1+ Hit ≥ 60%" in html
