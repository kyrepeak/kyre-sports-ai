from __future__ import annotations
from pathlib import Path
import cfb_game_total_step4_matchup_v3 as step4

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v17.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v162.py"
APP = ROOT / "app.py"

def _identity():
    return {"away":{"team":"Miami (FL)","logo":"away.png"},"home":{"team":"Wake Forest","logo":"home.png"}}

def _team(name):
    return {"team":name}

def _fd(o,d):
    return {"ready":True,"edge":None,"offense_rank":None,"defense_rank":None,"offense_value":o,"defense_value":d,"source":"multi-source","display_fallback":True}

def _fallback():
    return {
        "ready":True,
        "source":"multi-source: cfbstats.com + official team athletics audit",
        "away_offense":{"dimensions":{
            "passing":_fd("427.0","242.5"),"rushing":_fd("275.5","137.5"),"third_down":_fd("64.3%","44.8%"),
            "red_zone":_fd("80.0%","100.0%"),"sack_pressure":_fd("0.00/g","2.50/g"),"turnovers":_fd("1.00/g","0.50/g")}},
        "home_offense":{"dimensions":{
            "passing":_fd("290.5","145.5"),"rushing":_fd("194.5","57.5"),"third_down":_fd("46.2%","20.7%"),
            "red_zone":_fd("90.0%","100.0%"),"sack_pressure":_fd("1.00/g","1.50/g"),"turnovers":_fd("0.00/g","0.00/g")}},
    }

def test_v166_v3_fresh_owner_and_markers():
    assert step4.FROZEN_PREDECESSOR == "cfb_game_total_step4_matchup_v2"
    assert step4.STEP4_PRESENTATION_MARKER == "CFB_GAME_TOTAL_STEP4_MATCHUP_V3_MULTISOURCE_ACTIVE"
    assert step4.STEP4_DEPLOYMENT_MARKER == "CFB_GAME_TOTAL_STEP4_V3_FRESH_MULTISOURCE_ACTIVE"
    assert step4.MAY_MODIFY_PROJECTION is False
    assert step4.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

def test_v166_v3_loads_fallback_without_game(monkeypatch):
    calls=[]
    def fake(game,away,home):
        calls.append(game)
        return _fallback()
    monkeypatch.setattr(step4.multisource,"build_display_fallback",fake)
    html=step4.render_step4_html("CHECK",_identity(),_team("Miami (FL)"),_team("Wake Forest"),engine={"ready":True,"model_ready":False,"away_offense":{"dimensions":{}},"home_offense":{"dimensions":{}}})
    assert calls == [None]
    assert 'data-step4-state="READY"' in html
    assert 'data-step4-coverage="100"' in html
    assert 'data-step4-fallback-filled="12"' in html
    assert "Visible matchup coverage: 100%." in html
    assert "multi-source" in html.lower()

def test_v166_page_v17_owns_v3():
    s=PAGE.read_text()
    assert "import cfb_game_total_step4_matchup_v3 as step4_owner" in s
    assert "prior_v164.step4_owner = step4_owner" in s
    assert "STEP4_DEPLOYMENT_MARKER = step4_owner.STEP4_DEPLOYMENT_MARKER" in s

def test_v166_router_v162_and_runtime_app_activation():
    r=ROUTER.read_text()
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v161"' in r
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v17"' in r
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V166_STEP4_MULTISOURCE_ACTIVE"' in r
    a=APP.read_text()
    runtime=a.split("try:",1)[1]
    assert "from streamlit_memory_lazy_router_v162 import record_bootstrap_import_ms, render_app" in runtime
    assert "from streamlit_memory_lazy_router_v161 import record_bootstrap_import_ms, render_app" in a
