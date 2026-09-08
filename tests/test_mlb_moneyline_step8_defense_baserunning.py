"""Regression checks for Moneyline Step 8 defense + baserunning."""
import mlb_moneyline_hub_v174 as m


def test_fielding_metrics_derives_error_rate_and_fielding_pct():
    out=m._fielding_metrics({
        "gamesPlayed":100,
        "errors":45,
        "fielding":".988",
        "doublePlays":82,
    })
    assert out["games"]==100
    assert round(out["errors_per_game"],3)==0.45
    assert round(out["fielding_pct"],3)==0.988
    assert out["double_plays"]==82


def test_baserunning_metrics_derives_success_when_missing_percentage():
    out=m._baserunning_metrics({
        "gamesPlayed":100,
        "stolenBases":60,
        "caughtStealing":20,
    })
    assert out["attempts"]==80
    assert out["success_rate"]==0.75
    assert out["attempts_per_game"]==0.8


def test_defense_score_direction():
    strong=m._defense_score({
        "games":120,
        "fielding_pct":0.991,
        "errors_per_game":0.35,
    })
    weak=m._defense_score({
        "games":120,
        "fielding_pct":0.978,
        "errors_per_game":0.80,
    })
    assert strong["score"]>50
    assert weak["score"]<50


def test_defense_score_fails_closed_on_small_sample():
    out=m._defense_score({
        "games":10,
        "fielding_pct":0.995,
        "errors_per_game":0.20,
    })
    assert out["score"] is None


def test_baserunning_score_rewards_efficiency_and_penalizes_waste():
    strong=m._baserunning_score({
        "games":120,
        "attempts":100,
        "success_rate":0.86,
        "attempts_per_game":0.83,
    })
    weak=m._baserunning_score({
        "games":120,
        "attempts":100,
        "success_rate":0.60,
        "attempts_per_game":0.83,
    })
    assert strong["score"]>50
    assert weak["score"]<50


def test_baserunning_score_fails_closed_without_attempt_sample():
    out=m._baserunning_score({
        "games":100,
        "attempts":4,
        "success_rate":0.75,
        "attempts_per_game":0.04,
    })
    assert out["score"] is None


def test_composite_requires_both_components():
    out=m._composite(
        {"score":60,"reliability":1.0},
        {"score":None,"reliability":0.0},
    )
    assert out["score"] is None
    assert out["label"]=="DATA LIMITED / PENDING"


def test_composite_weights_defense_more_than_baserunning():
    out=m._composite(
        {"score":70,"reliability":1.0},
        {"score":40,"reliability":1.0},
    )
    assert out["score"]==59


def test_team_context_uses_separate_official_fielding_and_hitting(monkeypatch):
    def fake(team_id,group):
        if group=="fielding":
            return {
                "gamesPlayed":100,
                "errors":40,
                "fielding":".990",
                "doublePlays":80,
            }
        return {
            "gamesPlayed":100,
            "stolenBases":70,
            "caughtStealing":15,
            "stolenBasePercentage":".824",
        }

    monkeypatch.setattr(m,"_team_stat",fake)
    out=m._team_context(123,"Example Club")
    assert out["score"] is not None
    assert out["data_score"]>=m.MIN_DATA_SCORE
    assert out["fielding"]["errors"]==40
    assert out["running"]["stolen_bases"]==70


def test_team_context_fails_closed_without_baserunning_sample(monkeypatch):
    def fake(team_id,group):
        if group=="fielding":
            return {
                "gamesPlayed":100,
                "errors":40,
                "fielding":".990",
            }
        return {
            "gamesPlayed":100,
            "stolenBases":3,
            "caughtStealing":1,
        }

    monkeypatch.setattr(m,"_team_stat",fake)
    out=m._team_context(123,"Example Club")
    assert out["score"] is None
    assert "baserunning" in out["reason"].lower()


def test_overall_grade_direction_and_fail_closed():
    grade,cls,edge=m._overall_grade({"score":45},{"score":60})
    assert grade=="STRONG HOME DEFENSE/BASERUNNING EDGE"
    assert cls=="home"
    assert edge==15

    grade,cls,edge=m._overall_grade({"score":62},{"score":50})
    assert grade=="STRONG AWAY DEFENSE/BASERUNNING EDGE"
    assert cls=="away"
    assert edge==-12

    grade,cls,edge=m._overall_grade({"score":55},{"score":None})
    assert grade=="DATA LIMITED / PENDING"
    assert cls=="limited"
    assert edge is None


def test_step8_wrapper_preserves_step5l_live_owner(monkeypatch):
    seen={}
    original=m.prior._render_pregame_with_step7

    def fake_render(*args,**kwargs):
        seen["hook"]=m.prior._render_pregame_with_step7
        return "ok"

    monkeypatch.setattr(m.prior,"render_moneyline_hub",fake_render)
    monkeypatch.setattr(m.st,"markdown",lambda *args,**kwargs:None)

    out=m.render_moneyline_hub(None,None,None,None,None)

    assert out=="ok"
    assert seen["hook"] is m._render_pregame_with_step8
    assert m.prior._render_pregame_with_step7 is original
