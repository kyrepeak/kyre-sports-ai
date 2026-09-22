"""Regression checks for Moneyline Step 6 lineup strength + missing players."""
import mlb_moneyline_hub_v172 as m


def _row(pid, spot, avg, ops, name=None):
    return {
        "player_id": pid,
        "player_name": name or f"Player {pid}",
        "spot": spot,
        "avg": avg,
        "ops": ops,
    }


def test_weighted_metrics_uses_batting_order_weights():
    rows=[
        _row(1,1,".300",".900"),
        _row(2,2,".250",".750"),
        _row(3,3,".240",".700"),
    ]
    out=m._weighted_metrics(rows)
    assert out["usable"]==3
    assert out["weighted_avg"]>0.25
    assert out["weighted_ops"]>0.75


def test_lineup_score_rewards_strong_and_penalizes_weak():
    strong={"usable":9,"weighted_avg":0.285,"weighted_ops":0.840}
    weak={"usable":9,"weighted_avg":0.210,"weighted_ops":0.620}
    a=m._lineup_score(strong,9)
    b=m._lineup_score(weak,9)
    assert a["score"]>50
    assert a["label_cls"]=="strong"
    assert b["score"]<50
    assert b["label_cls"]=="weak"


def test_lineup_score_fails_closed_without_full_official_order():
    out=m._lineup_score({"usable":8,"weighted_avg":0.270,"weighted_ops":0.790},8)
    assert out["score"] is None
    assert out["label"]=="DATA LIMITED / PENDING"


def test_missing_context_classifies_not_active_and_active_not_starting():
    previous=[
        _row(1,1,".300",".900","Star One"),
        _row(2,2,".280",".820","Star Two"),
        _row(3,3,".250",".750","Returner"),
    ]
    current=[
        _row(3,1,".250",".750","Returner"),
        _row(4,2,".240",".700","New Four"),
    ]
    out=m._missing_context(current,previous,{2,3,4})
    assert [x["player_id"] for x in out["missing"]]==[1,2]
    assert [x["player_id"] for x in out["inactive"]]==[1]
    assert [x["player_id"] for x in out["active_not_starting"]]==[2]
    assert [x["player_id"] for x in out["additions"]]==[4]


def test_team_context_does_not_double_penalize_missing_players():
    current=[_row(i,i,".260",".780") for i in range(1,10)]
    previous=[_row(i,i,".260",".780") for i in range(1,9)] + [_row(99,9,".330",".980","Missing Star")]
    roster={"status":"VERIFIED","ids":set(range(1,10))}
    out=m._team_context(123,"Club",current,previous,roster)
    direct=m._lineup_score(m._weighted_metrics(current),9)
    assert out["score"]==direct["score"]
    assert len(out["missing"]["inactive"])==1


def test_team_context_tracks_continuity_delta():
    current=[_row(i,i,".250",".760") for i in range(1,10)]
    previous=[_row(i,i,".250",".710") for i in range(1,10)]
    roster={"status":"VERIFIED","ids":set(range(1,10))}
    out=m._team_context(123,"Club",current,previous,roster)
    assert round(out["continuity_delta"],3)==0.050
    assert out["quality"]==100


def test_overall_grade_direction_and_fail_closed():
    grade,cls,edge=m._overall_grade({"score":45},{"score":60})
    assert grade=="STRONG HOME LINEUP EDGE"
    assert cls=="home"
    assert edge==15

    grade,cls,edge=m._overall_grade({"score":62},{"score":50})
    assert grade=="STRONG AWAY LINEUP EDGE"
    assert cls=="away"
    assert edge==-12

    grade,cls,edge=m._overall_grade({"score":55},{"score":None})
    assert grade=="DATA LIMITED / PENDING"
    assert cls=="limited"
    assert edge is None


def test_step6_wrapper_preserves_step5l_live_owner(monkeypatch):
    seen={}
    original=m.prior._render_pregame

    def fake_prior_render(*args, **kwargs):
        seen["pregame_hook"]=m.prior._render_pregame
        seen["same_live_module"]=m.prior.MODEL_VERSION
        return "ok"

    monkeypatch.setattr(m.prior,"render_moneyline_hub",fake_prior_render)
    monkeypatch.setattr(m.st,"markdown",lambda *args,**kwargs:None)

    result=m.render_moneyline_hub(None,None,None,None,None)

    assert result=="ok"
    assert seen["pregame_hook"] is m._render_pregame_with_step6
    assert "STEP 5L" in seen["same_live_module"]
    assert m.prior._render_pregame is original
