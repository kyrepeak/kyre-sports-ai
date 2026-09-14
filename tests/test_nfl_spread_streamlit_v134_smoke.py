from __future__ import annotations

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def test_real_streamlit_apptest_executes_v134_spread_route() -> None:
    """Execute the real app entrypoint on the NFL -> Spread fast route."""
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.query_params["ks_nfl_sport"] = "NFL"
    at.query_params["ks_nfl_market"] = "Spread"

    # Use an offseason date so this proof focuses on the real Streamlit/router/page
    # runtime rather than repeating the expensive live-slate analytics certification.
    at.session_state["nfl_v1_date"] = date(2026, 2, 15)
    at.run(timeout=90)

    assert not at.exception

    cold = at.session_state["nfl_spread_cold_start_v132_last"]
    assert cold["active_page"] == "nfl_spread_hub_v3"
    assert cold["sportsbook_projection_influence"] == 0.0
    assert cold["stake_sizing_enabled"] is False
    assert cold["wager_actions_enabled"] is False

    assert at.query_params["ks_nfl_sport"] == "NFL"
    assert at.query_params["ks_nfl_market"] == "Spread"

    profiler = at.session_state["monster_performance_profiler_v1_last"]
    assert isinstance(profiler, dict)

    # V3 renders its hero before any remote schedule response is required, so this
    # confirms that the actual V3 page body executed even if a provider fails closed.
    rendered = "\n".join(str(item.value) for item in at.markdown)
    assert "NFL Spread" in rendered
    assert "Model + 5M Monte Carlo" in rendered
    assert "independent football fair line" in rendered
