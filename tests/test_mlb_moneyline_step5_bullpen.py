"""Regression checks for Moneyline Step 5 bullpen strength + availability."""
import mlb_moneyline_hub_v170 as m


def test_availability_labels():
    assert m._availability_label(None)=="PENDING"
    assert m._availability_label(0.95)=="READY"
    assert m._availability_label(0.80)=="MOSTLY READY"
    assert m._availability_label(0.60)=="TAXED"
    assert m._availability_label(0.40)=="HEAVILY TAXED"


def test_overall_grade_direction():
    grade,cls,edge=m._overall_grade({"score":45},{"score":60})
    assert grade=="STRONG HOME BULLPEN EDGE"
    assert cls=="home"
    assert edge==15

    grade,cls,edge=m._overall_grade({"score":63},{"score":50})
    assert grade=="STRONG AWAY BULLPEN EDGE"
    assert cls=="away"
    assert edge==-13


def test_overall_grade_fails_closed_if_either_side_missing():
    grade,cls,edge=m._overall_grade({"score":55},{"score":None})
    assert grade=="DATA LIMITED / PENDING"
    assert cls=="limited"
    assert edge is None


def test_starter_context_builds_recent_ip_per_start(monkeypatch):
    monkeypatch.setattr(m.step2,"_ctx",lambda result:{
        "away":{"id":11,"name":"Away SP","recent":{"starts":5,"ip":30.0}},
        "home":{"id":22,"name":"Home SP","recent":{"starts":4,"ip":22.0}},
    })
    out=m._starter_context({"game_pk":1})
    assert out["away"]["starter_id"]==11
    assert out["away"]["profile"]["recent5"]["ip_per_start"]==6.0
    assert out["home"]["profile"]["recent5"]["ip_per_start"]==5.5


def test_team_profile_passes_verified_inputs_to_bullpen_builder(monkeypatch):
    monkeypatch.setattr(m.bullpen,"fetch_active_pitchers",lambda *args:{
        "status":"VERIFIED","pitchers":[{"id":1},{"id":2},{"id":3},{"id":4}]
    })
    monkeypatch.setattr(m.bullpen,"fetch_team_pitcher_stats",lambda *args:{
        "status":"VERIFIED","rows":[]
    })
    monkeypatch.setattr(m.bullpen,"fetch_recent_workload",lambda *args:{
        "status":"VERIFIED","days":[]
    })

    seen={}
    def build(**kwargs):
        seen.update(kwargs)
        return {
            "reliever_count":6,
            "bullpen_path_score":64,
            "availability_index":0.88,
            "bullpen_data_score":80,
            "era":3.50,
            "whip":1.20,
            "k_pct":0.25,
            "bb_pct":0.07,
            "ready_count":4,
            "watch_count":2,
            "limited_count":0,
            "expected_bullpen_ip":3.4,
        }
    monkeypatch.setattr(m.bullpen,"build_bullpen_profile",build)

    starter={
        "starter_id":99,
        "starter_name":"Starter",
        "profile":{"recent5":{"status":"VERIFIED","ip_per_start":5.6}},
    }
    out=m._team_profile(123,"Example Club","2026-09-08",starter,{"status":"PENDING","frame":None})

    assert out["status"]=="VERIFIED"
    assert out["score"]==64
    assert out["label"]=="STRONG BULLPEN"
    assert seen["foundation"]["starter_id"]==99
    assert seen["opponent_team_id"]==123


def test_team_profile_fails_closed_on_incomplete_workload(monkeypatch):
    monkeypatch.setattr(m.bullpen,"fetch_active_pitchers",lambda *args:{"status":"VERIFIED","pitchers":[]})
    monkeypatch.setattr(m.bullpen,"fetch_team_pitcher_stats",lambda *args:{"status":"VERIFIED","rows":[]})
    monkeypatch.setattr(m.bullpen,"fetch_recent_workload",lambda *args:{"status":"PARTIAL","days":[]})
    monkeypatch.setattr(m.bullpen,"build_bullpen_profile",lambda **kwargs:{
        "reliever_count":7,
        "bullpen_path_score":70,
        "availability_index":0.80,
        "bullpen_data_score":85,
    })

    out=m._team_profile(
        123,
        "Example Club",
        "2026-09-08",
        {"starter_id":99,"starter_name":"Starter","profile":{}},
        {"status":"PENDING","frame":None},
    )
    assert out["status"]=="PENDING"
    assert out["score"] is None
    assert out["label"]=="DATA LIMITED / PENDING"
    assert "workload" in out["reason"].lower()


def test_team_profile_fails_closed_without_game_date():
    out=m._team_profile(
        123,
        "Example Club",
        "",
        {"starter_id":99,"starter_name":"Starter","profile":{}},
        {"status":"PENDING","frame":None},
    )
    assert out["score"] is None
    assert out["status"]=="PENDING"


def test_team_profile_fails_closed_without_team_id():
    out=m._team_profile(
        None,
        "Unknown Club",
        "2026-09-08",
        {},
        {"status":"PENDING","frame":None},
    )
    assert out["score"] is None
    assert out["label_cls"]=="limited"
