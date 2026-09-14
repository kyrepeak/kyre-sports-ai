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

    assert at.query_params["ks_nfl_sport"] == ["NFL"]
    assert at.query_params["ks_nfl_market"] == ["Spread"]

    profiler = at.session_state["monster_performance_profiler_v1_last"]
    assert isinstance(profiler, dict)

    # V3 renders its hero before any remote schedule response is required, so this
    # confirms that the actual V3 page body executed even if a provider fails closed.
    rendered = "\n".join(str(item.value) for item in at.markdown)
    assert "NFL Spread" in rendered
    assert "Model + 5M Monte Carlo" in rendered
    assert "independent football fair line" in rendered


def test_v3_normalizes_nested_matchup_html_before_markdown() -> None:
    """Prevent inherited team-panel HTML from becoming Markdown code blocks."""
    import nfl_spread_hub_v2 as prior
    import nfl_spread_hub_v3 as page

    game = {
        "game_id": "html-render-proof",
        "state": "pre",
        "season_type": "REGULAR SEASON",
        "tip_et": "8:15 PM ET",
        "venue": "Arrowhead Stadium",
        "broadcast": "ESPN / ABC",
        "away_team": "Denver Broncos",
        "away_abbr": "DEN",
        "away_record": "0-0",
        "away_logo": "",
        "home_team": "Kansas City Chiefs",
        "home_abbr": "KC",
        "home_record": "0-0",
        "home_logo": "",
    }
    market = {
        "ready": True,
        "books": [
            {
                "sportsbook": "FanDuel",
                "away_spread": 2.5,
                "away_price": -115,
                "home_spread": -2.5,
                "home_price": -105,
                "age_seconds": 0,
            }
        ],
        "projection_weight": 0.0,
    }

    raw = prior._matchup_card(game, market)
    normalized = page._html_fragment(raw)

    assert normalized.startswith('<article class="ksp2-matchup-card"')
    assert '\n<section class="ksp2-team-panel ksp2-away">' in normalized
    assert '\n<section class="ksp2-team-panel ksp2-home">' in normalized
    assert '\n    <section class="ksp2-team-panel' not in normalized
    assert page._html_fragment(
        page._summary_html(
            games=1,
            upcoming=1,
            market_ready=1,
            model_ready=1,
            mc_certified=1,
        )
    ).startswith('<div class="ksp3-summary">')
