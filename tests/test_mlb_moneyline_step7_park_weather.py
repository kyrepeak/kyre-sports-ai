"""Regression checks for Moneyline Step 7 park + weather run environment."""
import mlb_moneyline_hub_v173 as m


def test_park_run_proxy_uses_ops_and_runs_then_shrinks():
    home={"atBats":2200,"gamesPlayed":70,"runs":350,"hits":560,"avg":".255","ops":".780"}
    road={"atBats":2200,"gamesPlayed":70,"runs":280,"hits":520,"avg":".236","ops":".700"}
    out=m._park_run_proxy(home,road)
    assert out["factor"] is not None
    assert out["factor"]>1.0
    assert out["label"] in {"RUN-BOOSTING PARK PROXY","NEUTRAL PARK PROXY"}


def test_park_run_proxy_fails_closed_on_small_sample():
    home={"atBats":400,"gamesPlayed":20,"runs":100,"ops":".800"}
    road={"atBats":400,"gamesPlayed":20,"runs":80,"ops":".700"}
    out=m._park_run_proxy(home,road)
    assert out["factor"] is None
    assert out["label"]=="PARK SAMPLE PENDING"


def test_weather_profile_neutralizes_indoor_conditions():
    feed={
        "gameData":{
            "venue":{"fieldInfo":{"roofType":"Fixed Roof","turfType":"Artificial"}},
            "weather":{"temp":95,"condition":"Indoor","wind":"20 mph, Out To CF"},
        }
    }
    out=m._weather_profile(feed,{})
    assert out["indoor"] is True
    assert out["signal"]==0.0
    assert out["reliability"]==1.0


def test_weather_profile_flags_rain_language():
    feed={
        "gameData":{
            "venue":{"fieldInfo":{"roofType":"Open","turfType":"Grass"}},
            "weather":{"temp":72,"condition":"Rain Showers","wind":"8 mph, Out To RF"},
        }
    }
    out=m._weather_profile(feed,{})
    assert out["delay_risk"] is True
    assert out["wind_direction"]=="OUT"


def test_run_environment_score_direction():
    boost=m._run_environment_score(
        {"factor":1.06,"reliability":1.0},
        {"signal":0.6,"reliability":1.0},
    )
    suppress=m._run_environment_score(
        {"factor":0.94,"reliability":1.0},
        {"signal":-0.6,"reliability":1.0},
    )
    assert boost["score"]>50
    assert boost["label_cls"]=="hitter"
    assert suppress["score"]<50
    assert suppress["label_cls"]=="pitcher"


def test_run_environment_score_fails_closed_if_weather_missing():
    out=m._run_environment_score(
        {"factor":1.02,"reliability":0.8},
        {"signal":None,"reliability":0.0},
    )
    assert out["score"] is None
    assert out["label"]=="DATA LIMITED / PENDING"


def test_data_score_counts_only_park_weather_not_defense():
    score=m._data_score(
        True,
        True,
        {"factor":1.01,"reliability":1.0},
        {
            "temperature":80,
            "indoor":False,
            "wind_direction":"OUT",
            "condition":"Clear",
            "reliability":1.0,
        },
    )
    assert score==100


def test_game_context_fails_closed_without_park_sample(monkeypatch):
    monkeypatch.setattr(m.environment,"fetch_game_context",lambda pk:{
        "gameData":{
            "venue":{"id":5,"name":"Park","fieldInfo":{"roofType":"Open"}},
            "teams":{"home":{"id":123},"away":{"id":456}},
            "weather":{"temp":78,"condition":"Clear","wind":"7 mph, Out To CF"},
        }
    })
    monkeypatch.setattr(m.environment,"fetch_venue_context",lambda vid:{"id":vid,"name":"Park"})
    monkeypatch.setattr(m.environment,"fetch_team_split",lambda *args:{
        "atBats":300,"gamesPlayed":20,"runs":100,"ops":".750"
    })

    out=m._game_context(999)
    assert out["status"]=="PENDING"
    assert out["score"] is None
    assert "park sample" in out["reason"].lower()


def test_step7_wrapper_preserves_step5l_live_owner(monkeypatch):
    seen={}
    original=m.prior._render_pregame_with_step6

    def fake_render(*args,**kwargs):
        seen["hook"]=m.prior._render_pregame_with_step6
        return "ok"

    monkeypatch.setattr(m.prior,"render_moneyline_hub",fake_render)
    monkeypatch.setattr(m.st,"markdown",lambda *args,**kwargs:None)

    out=m.render_moneyline_hub(None,None,None,None,None)

    assert out=="ok"
    assert seen["hook"] is m._render_pregame_with_step7
    assert m.prior._render_pregame_with_step6 is original
