"""Pure-function regression checks for Moneyline Step 2.

These tests deliberately do not call MLB or mutate the frozen Moneyline chain.
"""
import mlb_moneyline_hub_v167 as m


def test_fip_is_deterministic():
    stat = {"homeRuns": 10, "baseOnBalls": 20, "hitByPitch": 2, "strikeOuts": 100, "inningsPitched": "100.0"}
    assert round(m._fip(stat), 2) == 2.26


def test_recent_uses_last_five_logged_appearances():
    logs = [{"inningsPitched": "5.0", "earnedRuns": 0, "hits": 3, "baseOnBalls": 1, "homeRuns": 0, "hitByPitch": 0, "strikeOuts": 5} for _ in range(6)]
    out = m._recent(logs)
    assert out["starts"] == 5
    assert out["ip"] == 25.0
    assert out["era"] == 0.0


def test_grade_thresholds_are_stable():
    assert m._grade(16)[0] == "ELITE HOME STARTER EDGE"
    assert m._grade(8)[0] == "STRONG HOME STARTER EDGE"
    assert m._grade(0)[0] == "NEUTRAL"
    assert m._grade(-8)[0] == "STRONG AWAY STARTER EDGE"
    assert m._grade(-16)[0] == "ELITE AWAY STARTER EDGE"
    assert m._grade(None)[0] == "DATA LIMITED / PENDING"


def test_quality_fails_closed_with_insufficient_evidence():
    score, metrics = m._quality({"era": "3.20"}, {"era": None})
    assert score is None
    assert metrics["era"] == 3.20
