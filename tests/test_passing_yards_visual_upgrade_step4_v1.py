from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(name: str) -> str:
    return (ROOT / name).read_text()

EXPECTED_LABELS = (
    "Sportsbook / source",
    "Passing yards line",
    "Over American odds",
    "Under American odds",
    "Price timestamp / note",
)

def test_step4_is_presentation_only_over_step3() -> None:
    body = read("nfl_passing_yards_hub_v49.py")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v48"' in body
    assert "PRESENTATION_ONLY = True" in body
    assert "MAY_MODIFY_PROJECTION = False" in body
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in body

def test_step4_preserves_exact_frozen_market_labels() -> None:
    wrapper = read("nfl_passing_yards_hub_v49.py")
    frozen = read("nfl_passing_yards_hub_v11.py")
    for label in EXPECTED_LABELS:
        assert label in wrapper
        assert label in frozen

def test_step4_preserves_frozen_widget_keys_and_market_owner() -> None:
    frozen = read("nfl_passing_yards_hub_v11.py")
    for suffix in ("_source", "_line", "_over", "_under", "_timestamp"):
        assert f'key=f"{{key}}{suffix}"' in frozen
    wrapper = read("nfl_passing_yards_hub_v49.py")
    assert "st.text_input(" not in wrapper
    assert "st.number_input(" not in wrapper

def test_step4_groups_existing_controls_with_scoped_css() -> None:
    body = read("nfl_passing_yards_hub_v49.py")
    assert 'data-passing-yards-market-polish="v49"' in body
    assert '[data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])' in body
    assert 'content:"STEP 10  •  LIVE MARKET CONTROL PANEL"' in body
    assert 'input[aria-label="Passing yards line"]' in body
    assert 'input[aria-label="Over American odds"]' in body
    assert 'input[aria-label="Under American odds"]' in body
    assert '@media(max-width:780px)' in body

def test_step4_router_advances_only_passing_yards() -> None:
    body = read("streamlit_memory_lazy_router_v195.py")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v194"' in body
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v49"' in body
    assert 'if sport != "NFL" or market != PASSING_MARKET:' in body
    assert "return prior.render_app()" in body

def test_step4_app_boots_v195() -> None:
    app = read("app.py")
    assert "from streamlit_memory_lazy_router_v195 import record_bootstrap_import_ms, render_app" in app
