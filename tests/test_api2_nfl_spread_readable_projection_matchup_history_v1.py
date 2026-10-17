from pathlib import Path

from nfl_spread_professional_intelligence_v2 import render_matchup_card

ROOT = Path(__file__).resolve().parents[1]


def _game():
    return {
        "game_id":"401772912","season_type":"REGULAR SEASON","tip_et":"9:30 AM ET",
        "venue":"Wembley Stadium","broadcast":"NFL Net","away_team":"Houston Texans",
        "away_abbr":"HOU","away_record":"1-4","home_team":"Jacksonville Jaguars",
        "home_abbr":"JAX","home_record":"4-1",
    }


def _market():
    return {"ready": True}


def _book():
    return {"sportsbook":"FanDuel","away_spread":2.5,"away_price":-110,"home_spread":-2.5,"home_price":-110}


def _analytics():
    return {
        "ready":True,"projected_away_margin":-3.66174,"away_win_probability":0.374,
        "home_win_probability":0.626,"away_cover_probability":0.464,"home_cover_probability":0.536,
        "simulated_away_margin_median":-4.0,"parameter_se":0.87,"residual_sd":12.97,
        "predictive_sd":12.999,"margin_quantiles":{"p05":-25.0,"p25":-12.0,"p50":-4.0,"p75":5.0,"p95":17.0},
        "push_probability":0.0,"simulations":5_000_000,"certified_run":True,"converged":True,
        "model_quality":"HIGH","away_cover_mc_se":0.00022,
    }


def _history():
    return {
        "ready":True,"display_only":True,"model_influence":0.0,"source":"nflverse","games":2,
        "series_summary":"Texans lead 2-0","average_margin":5.0,"ats_games":1,"ats_summary":"HOU 1-0 ATS",
        "meetings":[
            {"date":"Nov 9, 2025","score":"HOU 23 • JAX 20","winner_abbr":"HOU","margin":3.0,"spread_line":-2.5,"ats_winner":"HOU"},
            {"date":"Sep 21, 2025","score":"JAX 17 • HOU 24","winner_abbr":"HOU","margin":7.0,"spread_line":None,"ats_winner":None},
        ],
    }


def test_v2_replaces_technical_projection_with_plain_english_summary():
    html = render_matchup_card(_game(), _market(), _analytics(), book=_book(), history=_history())
    assert "WHAT THE MODEL EXPECTS" in html
    assert "Expected result" in html and "Jaguars by 3.7" in html
    assert "Most likely range" in html and "Texans by 5 → Jaguars by 12" in html
    assert "Wider possible range" in html
    assert "Chance team does not win" in html
    assert "PROJECTION RANGE" not in html
    assert "ADVANCED MODEL DETAILS" in html
    assert "Predictive SD" in html and "Parameter SE" in html


def test_v2_history_is_collapsed_and_display_only():
    html = render_matchup_card(_game(), _market(), _analytics(), book=_book(), history=_history())
    assert "MATCHUP HISTORY" in html
    assert "DISPLAY ONLY • 0.0% MODEL INFLUENCE" in html
    assert "Texans lead 2-0" in html
    assert "Last 2 meetings" in html
    assert "HOU 23 • JAX 20" in html
    assert "HOU 1-0 ATS" in html
    assert "<details" in html


def test_v8_is_additive_over_frozen_v7_and_active_router_points_to_v8():
    v8 = (ROOT / "nfl_spread_hub_v8.py").read_text(encoding="utf-8")
    router = (ROOT / "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py").read_text(encoding="utf-8")
    assert "import nfl_spread_hub_v7 as prior" in v8
    assert "load_matchup_history" in v8
    assert "history=history" in v8
    assert "import nfl_spread_hub_v8 as spread_v8" in router
    assert 'RUNTIME_SPREAD_PAGE = "nfl_spread_hub_v8"' in router
    assert "spread_v7 = spread_v8" in router
    assert 'return spread_v7.render_nfl_hub("Spread")' in router


def test_frozen_v7_and_v1_are_not_rewritten_by_v8():
    v8 = (ROOT / "nfl_spread_hub_v8.py").read_text(encoding="utf-8")
    v2 = (ROOT / "nfl_spread_professional_intelligence_v2.py").read_text(encoding="utf-8")
    assert "FROZEN_PRIOR = \"nfl_spread_hub_v7\"" in v8
    assert "import nfl_spread_professional_intelligence_v1 as frozen" in v2
