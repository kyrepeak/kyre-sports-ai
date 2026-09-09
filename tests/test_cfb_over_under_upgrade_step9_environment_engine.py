"""Regression checks for CFB O/U Upgrade Step 9 environment engine."""
from __future__ import annotations

import cfb_over_under_environment_engine_v1 as env


def _event():
    return {
        "id":"401858213",
        "competitions":[{
            "competitors":[
                {"homeAway":"home","team":{"id":"2390","displayName":"Miami Hurricanes","abbreviation":"MIA"}},
                {"homeAway":"away","team":{"id":"50","displayName":"Florida A&M Rattlers","abbreviation":"FAMU"}},
            ]
        }],
    }


def _game():
    return {
        "game_date":"2026-09-10",
        "away_team":"Florida A&M",
        "away_team_slug":"florida-am",
        "home_team":"Miami (FL)",
        "home_team_slug":"miami-fl",
    }


def _summary(temp=84,gust=8,precip=34,indoor=False):
    return {
        "header":{"id":"401858213","competitions":[{"id":"401858213"}]},
        "gameInfo":{
            "venue":{
                "id":"3948","fullName":"Hard Rock Stadium","indoor":indoor,
                "address":{"city":"Miami Gardens","state":"FL","zipCode":"33056","country":"USA"},
            },
            "weather":{"temperature":temp,"gust":gust,"precipitation":precip,"conditionId":"7"},
        },
    }


def _roster(team_id="50",flag=False):
    athlete={
        "id":"1","displayName":"Player One",
        "position":{"abbreviation":"QB"},
        "status":{"name":"Active" if not flag else "Out","type":"active" if not flag else "out"},
        "injuries":[] if not flag else [{"status":"Out"}],
    }
    return {
        "timestamp":"2026-09-09T00:50:05Z","status":"success",
        "athletes":[{"position":"offense","items":[athlete]}],
        "team":{"id":team_id},
    }


def test_exact_same_date_event_alias_match():
    payload={"events":[_event()]}
    found=env._resolve_event(payload,_game())
    assert found["id"]=="401858213"


def test_weather_parser_and_venue():
    s=_summary()
    w=env._weather(s); v=env._venue(s)
    assert w["ready"] is True
    assert w["temperature_f"]==84.0
    assert w["gust_mph"]==8.0
    assert w["precipitation_pct"]==34.0
    assert v["name"]=="Hard Rock Stadium"
    assert v["city"]=="Miami Gardens"


def test_mild_weather_has_zero_stress():
    stress=env._weather_stress(env._weather(_summary()),env._venue(_summary()))
    assert stress["total_stress"]==0.0
    assert stress["sigma_adjustment"]==0.0


def test_severe_weather_widens_sigma_but_is_capped():
    s=_summary(temp=20,gust=40,precip=100)
    stress=env._weather_stress(env._weather(s),env._venue(s))
    assert 0.0 < stress["total_stress"] <= 1.0
    assert 0.0 < stress["sigma_adjustment"] <= env.MAX_TOTAL_SIGMA_ADJUSTMENT


def test_indoor_venue_neutralizes_weather():
    s=_summary(temp=10,gust=50,precip=100,indoor=True)
    stress=env._weather_stress(env._weather(s),env._venue(s))
    assert stress["sigma_adjustment"]==0.0
    assert stress["indoor_weather_neutralized"] is True


def test_roster_audit_flags_but_never_gets_model_weight():
    audit=env._roster_audit(_roster(flag=True),"50")
    assert audit["ready"] is True
    assert audit["flagged_count"]==1
    assert audit["model_weight"]==0.0
    assert audit["injury_reporting_completeness_certified"] is False


def test_zero_flags_do_not_mean_healthy():
    audit=env._roster_audit(_roster(flag=False),"50")
    assert audit["flagged_count"]==0
    assert "zero reported flags does not certify" in audit["interpretation"]


def test_build_environment_engine_exact_event_weather_and_rosters(monkeypatch):
    monkeypatch.setattr(env,"_fetch_scoreboard",lambda day:({"events":[_event()]},[]))
    monkeypatch.setattr(env,"_fetch_summary",lambda event_id:(_summary(),[]))
    monkeypatch.setattr(env,"_fetch_roster",lambda team_id:(_roster(team_id),[]))
    out=env.build_environment_engine(_game(),{"team":"Florida A&M"},{"team":"Miami (FL)"})
    assert out["model_ready"] is True
    assert out["event_id"]=="401858213"
    assert out["away_espn_team_id"]=="50"
    assert out["home_espn_team_id"]=="2390"
    assert out["coverage"]==1.0
    assert out["roster_audit_coverage"]==1.0
    assert out["sigma_adjustment"]==0.0
    assert out["injury_model_weight"]==0.0
    assert out["availability_zero_flags_means_healthy"] is False


def test_build_environment_engine_fails_closed_without_event(monkeypatch):
    monkeypatch.setattr(env,"_fetch_scoreboard",lambda day:({"events":[]},[]))
    out=env.build_environment_engine(_game(),{}, {})
    assert out["model_ready"] is False
    assert out["sigma_adjustment"]==0.0
    assert "exact same-date ESPN event" in out["reason"]


def test_apply_to_raw_preserves_projection_and_reliability():
    base={
        "version":"STEP8","ready":True,
        "projected_away_points":20.0,"projected_home_points":27.0,"projected_total":47.0,
        "structural_total_sigma":14.0,"reliability":0.72,"analysis_line":50.5,"components":{},
    }
    engine={
        "model_ready":True,"coverage":1.0,"roster_audit_coverage":1.0,
        "sigma_adjustment":0.5,"weather_stress":{"total_stress":0.4},
    }
    out=env.apply_to_raw(base,engine)
    assert out["upgrade_step9_applied"] is True
    assert out["projected_away_points"]==20.0
    assert out["projected_home_points"]==27.0
    assert out["projected_total"]==47.0
    assert out["structural_total_sigma"]==14.5
    assert out["reliability"]==0.72
    assert out["components"]["step9_projected_total_adjustment"]==0.0
    assert out["components"]["step9_injury_points_adjustment"]==0.0
    assert out["analysis_line_environment_weight"]==0.0
    assert out["projected_total_environment_weight"]==0.0
    assert out["injury_model_weight"]==0.0


def test_apply_fails_closed_when_weather_not_ready():
    base={"version":"STEP8","ready":True,"projected_total":47.0}
    out=env.apply_to_raw(base,{"model_ready":False,"reason":"weather missing"})
    assert out["upgrade_step9_applied"] is False
    assert out["projected_total"]==47.0
    assert out["environment_engine_reason"]=="weather missing"
