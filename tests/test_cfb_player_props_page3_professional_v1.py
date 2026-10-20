from __future__ import annotations

import copy
import importlib
from pathlib import Path
from types import SimpleNamespace


def _m():
    return importlib.import_module("cfb_player_props_page3_professional_v1")


def _rows():
    return [
        {"event_id":"g6","official_player_id":"p1","opponent_team_id":"t9","game_date":"2026-10-17","value":312,"pass_attempts":39,"completions":27,"passing_touchdowns":3,"interceptions":1,"source":"espn","observed_at_utc":"2026-10-17T23:00:00Z"},
        {"event_id":"g5","official_player_id":"p1","opponent_team_id":"t8","game_date":"2026-10-10","value":284,"pass_attempts":36,"completions":25,"source":"ncaa_official","observed_at_utc":"2026-10-10T23:00:00Z"},
        {"event_id":"g4","official_player_id":"p1","opponent_team_id":"t9","game_date":"2026-10-03","value":221,"source":"espn","observed_at_utc":"2026-10-03T23:00:00Z"},
        {"event_id":"g3","official_player_id":"p1","opponent_team_id":"t7","game_date":"2026-09-26","value":301,"source":"espn","observed_at_utc":"2026-09-26T23:00:00Z"},
        {"event_id":"g2","official_player_id":"p1","opponent_team_id":"t6","game_date":"2026-09-19","value":267,"source":"espn","observed_at_utc":"2026-09-19T23:00:00Z"},
        {"event_id":"g1","official_player_id":"p1","opponent_team_id":"t5","game_date":"2026-09-12","value":198,"source":"espn","observed_at_utc":"2026-09-12T23:00:00Z"},
    ]


def _packet(*, observations=(), history=None):
    return {
        "history_rows":tuple(_rows() if history is None else history),
        "projection":{"projection":280,"model_ready":True,"sample_count":6},
        "line_lab":{"line":250.5,"margin":29.5,"over_probability":0.71,"under_probability":0.29,"model_ready":True},
        "market":{"consensus_line":248.5,"observations":observations,"book_count":len(observations)},
        "quality":{},
        "sportsbook_projection_influence":0.0,
    }


def test_recent_windows_return_honest_last3_and_last5_samples():
    m=_m()
    last3=m.build_recent_window(_rows()[:2],limit=3,selected_line=250.5)
    last5=m.build_recent_window(_rows(),limit=5,selected_line=250.5)
    assert last3["sample_size"] == 2
    assert last3["hits"] == 2
    assert last5["sample_size"] == 5
    assert last5["hits"] == 4
    assert round(last5["average"],1) == 277.0
    assert last5["hit_rate"] == 0.8


def test_recent_window_hit_rate_uses_only_numeric_production():
    m=_m()
    rows=[{"value":280},{"value":None},{"value":"bad"},{"value":260}]
    out=m.build_recent_window(rows,limit=5,selected_line=270.5)
    assert out["sample_size"] == 2
    assert out["hits"] == 1
    assert out["hit_rate"] == 0.5


def test_direct_opponent_requires_exact_opponent_team_id():
    m=_m()
    out=m.build_direct_opponent(_rows(),opponent_team_id="t9",selected_line=250.5)
    assert out["sample_size"] == 2
    assert [r["event_id"] for r in out["rows"]] == ["g6","g4"]
    assert out["hits"] == 1


def test_team_matchup_does_not_masquerade_as_player_h2h():
    m=_m()
    rows=[
        {"event_id":"team1","opponent_team_id":"t9","official_player_id":"other-qb","value":290},
        {"event_id":"direct1","opponent_team_id":"t9","official_player_id":"p1","value":310},
    ]
    out=m.build_team_matchup(rows,opponent_team_id="t9",selected_player_id="p1")
    assert out["label"] == "Team Matchup History"
    assert out["sample_size"] == 1
    assert out["rows"][0]["official_player_id"] == "other-qb"


def test_quarterback_detail_omits_unverified_optional_stats_instead_of_zero():
    m=_m()
    out=m.build_recent_window(_rows()[1:3],limit=3,selected_line=250.5)
    first=out["rows"][0]
    second=out["rows"][1]
    assert first["completion_percentage"] == round(25/36*100,1)
    assert first["yards_per_attempt"] == round(284/36,2)
    assert "passing_touchdowns" not in first
    assert "pass_attempts" not in second
    assert "completion_percentage" not in second


def test_opponent_vs_role_unavailable_has_no_directional_claim():
    m=_m()
    packet={"history_rows":(),"projection":{"projection":280,"model_ready":True,"sample_count":5},"line_lab":{"line":250.5,"margin":29.5,"over_probability":0.70,"under_probability":0.30,"model_ready":True},"market":{"observations":(),"book_count":0},"quality":{},"sportsbook_projection_influence":0.0}
    view=m.build_professional_view({"opponent_team_id":"t9","official_player_id":"p1"},packet,selected_line=250.5)
    assert view["opponent_vs_role"]["available"] is False
    assert "direction" not in view["opponent_vs_role"]


def test_decision_view_uses_frozen_projection_and_selected_line_only():
    m=_m()
    view=m.build_professional_view({"opponent_team_id":"t9","official_player_id":"p1"},_packet(),selected_line=250.5)
    assert view["decision"]["projection"] == 280
    assert view["decision"]["selected_line"] == 250.5
    assert view["decision"]["margin"] == 29.5
    assert view["decision"]["lean"] == "OVER"
    assert view["decision"]["over_probability"] == 0.71


def test_decision_distinguishes_selected_margin_from_market_consensus_margin():
    m=_m()
    view=m.build_professional_view({"opponent_team_id":"t9","official_player_id":"p1"},_packet(),selected_line=250.5)
    assert view["decision"]["margin"] == 29.5
    assert view["decision"]["market_consensus"] == 248.5
    assert view["decision"]["market_margin"] == 31.5


def test_professional_view_does_not_mutate_input_packet():
    m=_m()
    packet=_packet()
    before=copy.deepcopy(packet)
    m.build_professional_view({"opponent_team_id":"t9","official_player_id":"p1"},packet,selected_line=250.5)
    assert packet == before


def test_sportsbook_projection_influence_remains_zero():
    m=_m()
    assert m.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_professional_view_reports_actual_approved_sources_by_field_only():
    m=_m()
    observations=(
        SimpleNamespace(provider="FanDuel",sportsbook="FanDuel",side="over",line=250.5,price=-110,observed_at_utc="2026-10-20T20:00:00Z"),
        SimpleNamespace(provider="Odds-API.io",sportsbook="DraftKings",side="under",line=251.5,price=-105,observed_at_utc="2026-10-20T20:03:00Z"),
        SimpleNamespace(provider="SportsGameOdds",sportsbook="BetMGM",side="over",line=252.5,price=-115,observed_at_utc="2026-10-20T20:02:00Z"),
    )
    packet=_packet(observations=observations,history=_rows()[:2])
    packet["availability"]={"state":"ACTIVE","source":"RotoWire"}
    view=m.build_professional_view({"opponent_team_id":"t9","official_player_id":"p1"},packet,selected_line=250.5)
    props=view["source_status"]["player_props"]
    history_status=view["source_status"]["history"]
    availability=view["source_status"]["availability"]
    assert props["active_provider_ids"] == ("direct_sportsbook_feed","the_odds_api")
    assert props["actual_provider_labels"] == ("FanDuel","Odds-API.io","SportsGameOdds")
    assert "sportsdataio" not in props["active_provider_ids"]
    assert history_status["active_provider_ids"] == ("ncaa_official","espn")
    assert availability["active_provider_ids"] == ("rotowire",)


def test_team_matchup_loader_uses_reachable_runtime_history_router():
    m=_m()
    seen={}
    def fake_loader(row,game):
        seen["row"]=dict(row); seen["game"]=dict(game)
        return {
            "status":"VERIFIED_HISTORY",
            "history_ready":True,
            "recent_meetings":[
                {"event_id":"old1","date":"2025-10-01","away_points":24,"home_points":31,"combined_total":55,"source":"ESPN exact-team schedule history"}
            ],
            "sources_verified":["ESPN"],
            "observed_at":"2026-10-20T21:00:00Z",
        }
    context={
        "official_game_id":"future1","away_team":"Away U","home_team":"Home U",
        "away_team_id":"101","home_team_id":"202",
        "game":{"espn_event_id":"future1","away_espn_team_id":"101","home_espn_team_id":"202","away_team":"Away U","home_team":"Home U"},
    }
    out=m.load_team_matchup_history(context,history_loader=fake_loader)
    assert seen["game"]["away_espn_team_id"] == "101"
    assert seen["game"]["home_espn_team_id"] == "202"
    assert out["available"] is True
    assert out["status"] == "VERIFIED_HISTORY"
    assert out["rows"][0]["event_id"] == "old1"
    assert out["rows"][0]["source"] == "ESPN exact-team schedule history"
    assert out["sources"] == ("ESPN",)


def test_professional_view_uses_loaded_team_history_when_context_has_no_rows(monkeypatch):
    m=_m()
    monkeypatch.setattr(m,"load_team_matchup_history",lambda context:{
        "available":True,"status":"VERIFIED_HISTORY","sources":("ESPN",),"observed_at":"2026-10-20T21:00:00Z",
        "rows":({"event_id":"old1","date":"2025-10-01","source":"ESPN exact-team schedule history"},),
    })
    context={"opponent_team_id":"t9","official_player_id":"p1","away_team":"A","home_team":"B","away_team_id":"1","home_team_id":"2"}
    view=m.build_professional_view(context,_packet(),selected_line=250.5)
    assert view["team_matchup"]["available"] is True
    assert view["team_matchup"]["sample_size"] == 1
    assert view["team_matchup"]["rows"][0]["event_id"] == "old1"


def test_page3_source_has_professional_ui_contract():
    source=(Path(__file__).resolve().parents[1]/"cfb_player_props_page3_v1.py").read_text()
    for token in (
        "cfb_player_props_page3_professional_v1",
        "MODEL DECISION",
        "LINE LAB",
        "LAST 3",
        "LAST 5",
        "DIRECT PLAYER VS OPPONENT",
        "TEAM MATCHUP HISTORY",
        "OPPONENT VS ROLE",
        "SPORTSBOOK MARKET",
        "WHY THE MODEL SEES IT THIS WAY",
        "DATA QUALITY & SOURCES",
        "ACTIVE FIELD SOURCES",
        "← Back to Game Props",
        "↑ TOP",
    ):
        assert token in source
    assert "st.number_input" not in source
    assert "st.text_input" not in source
    assert "build_professional_view" in source


def test_page3_reads_slider_widget_state_before_first_decision_and_keeps_market_margin_distinct():
    source=(Path(__file__).resolve().parents[1]/"cfb_player_props_page3_v1.py").read_text()
    assert 'slider_state_key=f"cfbpp3_slider_{identity}"' in source
    assert 'widget_line=st.session_state.get(slider_state_key)' in source
    assert source.index('widget_line=st.session_state.get(slider_state_key)') < source.index('_decision(view)')
    assert 'get("market_margin")' in source
