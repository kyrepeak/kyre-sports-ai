from pathlib import Path

import mlb_matchup_player_v24 as step1


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _complete_fields(source="✅ CONFIRMED LINEUP", slot=2, lineup_role=True):
    return {
        "player_id": 592450,
        "player_name": "Example Hitter",
        "team": "Example Team",
        "opponent": "Opponent Team",
        "game_pk": 123456,
        "game_date": "2026-09-02",
        "first_pitch": "7:10 PM",
        "venue": "Example Park",
        "game_status": "Preview",
        "lineup_source": source,
        "lineup_role": lineup_role,
        "slot": slot,
        "side": "home",
        "starter_name": "Example Starter",
        "starter_id": 654321,
        "starter_hand": "L",
        "batter_hand": "R",
        "season_stat": {
            "plateAppearances": 500,
            "atBats": 450,
            "hits": 130,
            "avg": ".289",
            "gamesPlayed": 130,
        },
        "player_person": {"id": 592450},
        "starter_person": {"id": 654321},
    }


def test_complete_confirmed_foundation_is_100_completeness():
    score, components = step1._quality_score(_complete_fields())
    assert score == 100
    assert sum(maximum for _, maximum in components.values()) == 100
    assert step1._quality_label(score) == "ELITE DATA"


def test_projected_lineup_scores_below_confirmed_but_remains_high_quality():
    confirmed, _ = step1._quality_score(_complete_fields())
    projected, _ = step1._quality_score(_complete_fields(source="🕒 PROJECTED LINEUP"))
    assert confirmed == 100
    assert projected == 95
    assert projected < confirmed
    assert step1._quality_label(projected) == "ELITE DATA"


def test_bench_player_does_not_receive_batting_slot_credit():
    score, components = step1._quality_score(
        _complete_fields(source="🪑 BENCH / ACTIVE ROSTER", slot=99, lineup_role=False)
    )
    assert components["Lineup readiness"] == (2, 25)
    assert score == 77
    assert step1._quality_label(score) == "USABLE DATA"


def test_missing_starter_context_is_penalized_without_fabrication():
    fields = _complete_fields()
    fields.update({
        "starter_name": "TBD",
        "starter_id": None,
        "starter_hand": "—",
        "starter_person": {},
    })
    score, components = step1._quality_score(fields)
    assert components["Starter + handedness"] == (4, 20)
    assert score == 81
    assert score < 100


def test_step1_declares_zero_probability_impact():
    assert step1.PROBABILITY_IMPACT == "NONE"
    source = _text("mlb_matchup_player_v24.py")
    for forbidden in (
        "def _calibration_from_verdict",
        "def _shrink",
        "def _simulate",
        "p_one_plus_pre_matchup",
        "p_two_plus",
        "fair_odds",
    ):
        assert forbidden not in source
    assert "probability impact: NONE" in source


def test_step1_keeps_new_steps_together_and_legacy_separate():
    source = _text("mlb_matchup_player_v24.py")
    assert 'V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"' in source
    assert 'LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"' in source
    assert "with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):" in source
    assert "with st.expander(LEGACY_AUDIT_LABEL, expanded=False):" in source
    assert "STEP 1 • PLAYER + OPPORTUNITY FOUNDATION" in source
    assert "Ready for Step 9 PA model" in source


def test_current_frozen_v1_presentation_is_imported_not_reimplemented():
    source = _text("mlb_matchup_player_v24.py")
    assert "import mlb_matchup_player_v20 as frozen_detail" in source
    assert "import mlb_matchup_player_v22 as clean" in source
    assert "frozen_detail.render_player_layer" in source
    assert "clean._render_snapshot" in source


def test_hub_routes_to_v2_step1_and_keeps_rankings_frozen():
    hub = _text("mlb_matchup_hub_v30.py")
    entry = _text("mlb_matchup_hub_v27.py")
    assert "import mlb_matchup_player_v24 as player_layer" in hub
    assert "import mlb_matchup_rankings_v21 as rankings" in hub
    assert 'FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")' in hub
    assert "from mlb_matchup_hub_v30 import FROZEN_MATCHUP_CHAIN, VERSION, render_matchup_hub" in entry


def test_historical_v1_workflow_is_isolated_from_future_v2_prs():
    workflow = _text(".github/workflows/mlb-matchup-unified-intelligence-v1.yml")
    assert "github.head_ref == 'mlb-matchup-unified-intelligence-v1'" in workflow
