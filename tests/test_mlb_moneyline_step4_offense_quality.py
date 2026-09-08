"""Regression checks for Moneyline Step 4 team offense quality."""
import mlb_moneyline_hub_v169 as m


def test_metrics_derives_team_rate_stats():
    stat={
        "gamesPlayed":100,
        "runs":500,
        "homeRuns":120,
        "plateAppearances":3800,
        "baseOnBalls":340,
        "strikeOuts":800,
        "avg":".255",
        "obp":".325",
        "slg":".430",
        "ops":".755",
    }
    out=m._metrics(stat)
    assert out["games"]==100
    assert out["rpg"]==5.0
    assert out["hrpg"]==1.2
    assert round(out["bb_pct"],4)==round(340/3800,4)
    assert round(out["k_pct"],4)==round(800/3800,4)


def test_score_direction_rewards_better_offense():
    strong={
        "games":120,"rpg":5.4,"ops":0.820,"obp":0.345,"slg":0.475,
        "hrpg":1.45,"bb_pct":0.100,"k_pct":0.190,
    }
    weak={
        "games":120,"rpg":3.5,"ops":0.650,"obp":0.285,"slg":0.350,
        "hrpg":0.75,"bb_pct":0.060,"k_pct":0.285,
    }
    a=m._score(strong)
    b=m._score(weak)
    assert a["score"]>50
    assert a["label_cls"]=="strong"
    assert b["score"]<50
    assert b["label_cls"]=="weak"


def test_score_fails_closed_on_small_sample():
    metrics={
        "games":5,"rpg":6.0,"ops":0.900,"obp":0.380,"slg":0.520,
        "hrpg":1.8,"bb_pct":0.120,"k_pct":0.170,
    }
    out=m._score(metrics)
    assert out["score"] is None
    assert out["label"]=="DATA LIMITED / PENDING"


def test_score_fails_closed_on_insufficient_components():
    metrics={"games":100,"rpg":5.0,"ops":0.760,"obp":0.330}
    out=m._score(metrics)
    assert out["score"] is None
    assert out["components"]==3


def test_team_context_uses_official_team_hitting(monkeypatch):
    monkeypatch.setattr(m,"_team_hitting",lambda team_id:{
        "gamesPlayed":100,
        "runs":490,
        "homeRuns":130,
        "plateAppearances":3900,
        "baseOnBalls":350,
        "strikeOuts":780,
        "avg":".260",
        "obp":".330",
        "slg":".440",
        "ops":".770",
    })
    out=m._team_ctx(123,"Example Club")
    assert out["team_id"]==123
    assert out["team_name"]=="Example Club"
    assert out["score"] is not None
    assert out["quality"]==100


def test_team_context_fails_closed_without_team_id():
    out=m._team_ctx(None,"Unknown Club")
    assert out["score"] is None
    assert out["label_cls"]=="limited"
    assert out["quality"]==0


def test_overall_grade_direction():
    grade,cls,edge=m._overall_grade({"score":45},{"score":60})
    assert grade=="STRONG HOME OFFENSE EDGE"
    assert cls=="home"
    assert edge==15

    grade,cls,edge=m._overall_grade({"score":62},{"score":50})
    assert grade=="STRONG AWAY OFFENSE EDGE"
    assert cls=="away"
    assert edge==-12


def test_overall_grade_fails_closed_if_either_team_missing():
    grade,cls,edge=m._overall_grade({"score":55},{"score":None})
    assert grade=="DATA LIMITED / PENDING"
    assert cls=="limited"
    assert edge is None
