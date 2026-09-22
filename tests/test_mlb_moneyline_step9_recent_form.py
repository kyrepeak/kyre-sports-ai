"""Regression checks for Moneyline Step 9 recent team form + schedule context."""
import mlb_moneyline_hub_v175 as m


def _game(day,team_score,opp_score,win=None):
    if win is None:
        win=team_score>opp_score
    return {
        "date":day,
        "team_score":team_score,
        "opponent_score":opp_score,
        "run_diff":team_score-opp_score,
        "win":bool(win),
        "loss":team_score<opp_score,
        "doubleheader":"N",
        "game_number":1,
    }


def test_window_summary_builds_record_and_run_diff():
    games=[
        _game("2026-09-07",5,2),
        _game("2026-09-06",2,3),
        _game("2026-09-05",7,1),
        _game("2026-09-04",4,5),
        _game("2026-09-03",6,4),
    ]
    out=m._window_summary(games,5)
    assert out["games"]==5
    assert out["wins"]==3
    assert out["losses"]==2
    assert out["run_diff"]==9
    assert round(out["run_diff_per_game"],2)==1.80


def test_streak_tracks_latest_result_run():
    games=[
        _game("2026-09-07",5,2),
        _game("2026-09-06",4,1),
        _game("2026-09-05",3,2),
        _game("2026-09-04",1,2),
    ]
    out=m._streak(games)
    assert out["label"]=="W3"


def test_schedule_context_counts_rest_density_and_consecutive_days():
    games=[
        _game("2026-09-07",5,2),
        _game("2026-09-06",4,1),
        _game("2026-09-05",3,2),
        _game("2026-09-04",4,3),
        _game("2026-09-03",2,1),
        _game("2026-09-02",6,5),
    ]
    out=m._schedule_context(games,"2026-09-08")
    assert out["rest_days"]==0
    assert out["games_last3"]==3
    assert out["games_last7"]==6
    assert out["consecutive_days"]==6
    assert out["label"]=="DENSE SCHEDULE"


def test_schedule_context_detects_rest():
    games=[
        _game("2026-09-05",5,2),
        _game("2026-09-04",4,1),
    ]
    out=m._schedule_context(games,"2026-09-08")
    assert out["rest_days"]==2
    assert out["label"]=="EXTENDED REST"


def test_schedule_context_counts_doubleheader_dates():
    games=[
        {**_game("2026-09-07",5,2),"game_number":2,"doubleheader":"Y"},
        {**_game("2026-09-07",2,1),"game_number":1,"doubleheader":"Y"},
        _game("2026-09-06",4,3),
    ]
    out=m._schedule_context(games,"2026-09-08")
    assert out["doubleheaders_last7"]==1
    assert out["games_last3"]==3


def test_form_score_rewards_wins_and_run_differential():
    hot=m._form_score(
        {"games":5,"win_pct":0.80},
        {"games":10,"win_pct":0.70,"run_diff_per_game":2.0},
    )
    cold=m._form_score(
        {"games":5,"win_pct":0.20},
        {"games":10,"win_pct":0.30,"run_diff_per_game":-2.0},
    )
    assert hot["score"]>50
    assert hot["label_cls"]=="strong"
    assert cold["score"]<50
    assert cold["label_cls"]=="weak"


def test_form_score_fails_closed_with_too_few_games():
    out=m._form_score(
        {"games":5,"win_pct":0.80},
        {"games":7,"win_pct":0.70,"run_diff_per_game":2.0},
    )
    assert out["score"] is None
    assert out["label"]=="DATA LIMITED / PENDING"


def test_team_schedule_uses_strict_pregame_final_filter(monkeypatch):
    payload={
        "dates":[
            {
                "date":"2026-09-07",
                "games":[
                    {
                        "gamePk":111,
                        "officialDate":"2026-09-07",
                        "status":{"detailedState":"Final"},
                        "teams":{
                            "away":{"team":{"id":123},"score":5},
                            "home":{"team":{"id":456},"score":2},
                        },
                        "gameNumber":1,
                        "doubleHeader":"N",
                    }
                ],
            },
            {
                "date":"2026-09-08",
                "games":[
                    {
                        "gamePk":222,
                        "officialDate":"2026-09-08",
                        "status":{"detailedState":"Final"},
                        "teams":{
                            "away":{"team":{"id":123},"score":9},
                            "home":{"team":{"id":456},"score":0},
                        },
                        "gameNumber":1,
                        "doubleHeader":"N",
                    }
                ],
            },
            {
                "date":"2026-09-06",
                "games":[
                    {
                        "gamePk":333,
                        "officialDate":"2026-09-06",
                        "status":{"detailedState":"In Progress"},
                        "teams":{
                            "away":{"team":{"id":123},"score":3},
                            "home":{"team":{"id":456},"score":3},
                        },
                        "gameNumber":1,
                        "doubleHeader":"N",
                    }
                ],
            },
        ]
    }
    monkeypatch.setattr(m,"_json",lambda url:payload)
    m._team_schedule.clear()

    out=m._team_schedule(123,"2026-09-08")

    assert out["status"]=="VERIFIED"
    assert [g["game_pk"] for g in out["games"]]==[111]
    assert out["games"][0]["win"] is True


def test_data_score_requires_verified_asof_evidence():
    payload={"status":"VERIFIED"}
    l10={"games":10,"win_pct":0.6,"run_diff_per_game":1.0}
    schedule={"rest_days":0}
    assert m._data_score(payload,l10,schedule,"2026-09-08")==100
    assert m._data_score(payload,l10,schedule,"")<m.MIN_DATA_SCORE


def test_overall_grade_direction_and_fail_closed():
    grade,cls,edge=m._overall_grade({"score":45},{"score":60})
    assert grade=="STRONG HOME RECENT-FORM EDGE"
    assert cls=="home"
    assert edge==15

    grade,cls,edge=m._overall_grade({"score":62},{"score":50})
    assert grade=="STRONG AWAY RECENT-FORM EDGE"
    assert cls=="away"
    assert edge==-12

    grade,cls,edge=m._overall_grade({"score":55},{"score":None})
    assert grade=="DATA LIMITED / PENDING"
    assert cls=="limited"
    assert edge is None


def test_schedule_density_is_not_added_to_form_score():
    base_l5={"games":5,"win_pct":0.6}
    base_l10={"games":10,"win_pct":0.6,"run_diff_per_game":1.0}
    a=m._form_score(base_l5,base_l10)
    b=m._form_score(dict(base_l5),dict(base_l10))
    assert a==b


def test_step9_wrapper_preserves_step5l_live_owner(monkeypatch):
    seen={}
    original=m.prior._render_pregame_with_step8

    def fake_render(*args,**kwargs):
        seen["hook"]=m.prior._render_pregame_with_step8
        return "ok"

    monkeypatch.setattr(m.prior,"render_moneyline_hub",fake_render)
    monkeypatch.setattr(m.st,"markdown",lambda *args,**kwargs:None)

    out=m.render_moneyline_hub(None,None,None,None,None)

    assert out=="ok"
    assert seen["hook"] is m._render_pregame_with_step9
    assert m.prior._render_pregame_with_step8 is original
