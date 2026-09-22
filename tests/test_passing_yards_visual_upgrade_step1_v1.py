from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(name: str) -> str:
    return (ROOT / name).read_text()

def test_step1_top_control_deck_is_presentation_only() -> None:
    body = read("nfl_passing_yards_hub_v46.py")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v45"' in body
    assert "PRESENTATION_ONLY = True" in body
    assert "MAY_MODIFY_PROJECTION = False" in body
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in body
    assert 'TOP_CONTAINER_KEY = "kyre_passing_yards_top_v46"' in body

def test_step1_groups_date_and_matchup_and_suppresses_duplicate_date() -> None:
    body = read("nfl_passing_yards_hub_v46.py")
    assert 'date_col, matchup_col = st.columns([0.82, 2.18], gap="small")' in body
    assert 'if str(label) == "NFL Passing Yards slate date":' in body
    assert "return resolved_day" in body
    assert "navigation._verified_matchup_labels(chosen_day)" in body
    assert "st.session_state[rolling.V8_MATCHUP_KEY] = chosen" in body

def test_step1_has_dead_space_cleanup_contract() -> None:
    body = read("nfl_passing_yards_hub_v46.py")
    assert 'data-passing-yards-top-polish="v46"' in body
    assert '[data-testid="stElementContainer"]:has(> div:empty)' in body
    assert 'gap:.72rem!important' in body

def test_step1_router_changes_only_passing_yards() -> None:
    body = read("streamlit_memory_lazy_router_v192.py")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v191"' in body
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v46"' in body
    assert 'if sport != "NFL" or market != PASSING_MARKET:' in body
    assert "return prior.render_app()" in body
    assert "passing_router.PASSING_HUB = PASSING_HUB" in body

def test_step1_app_boots_v192() -> None:
    app = read("app.py")
    assert "from streamlit_memory_lazy_router_v192 import record_bootstrap_import_ms, render_app" in app
