from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from nfl_spread_professional_intelligence_v1 import render_matchup_card


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py"
HYGIENE = ROOT / "streamlit_route_hygiene_v1.py"


def _load_hygiene():
    assert HYGIENE.exists(), "route hygiene module must exist"
    spec = spec_from_file_location("streamlit_route_hygiene_v1_test", HYGIENE)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _game():
    return {
        "game_id": "401772999",
        "state": "pre",
        "season_type": "REGULAR SEASON",
        "tip_et": "1:00 PM ET",
        "venue": "Mercedes-Benz Stadium",
        "broadcast": "FOX",
        "away_team": "Chicago Bears",
        "away_abbr": "CHI",
        "away_record": "3-2",
        "away_logo": "https://example.com/chi.png",
        "home_team": "Atlanta Falcons",
        "home_abbr": "ATL",
        "home_record": "2-3",
        "home_logo": "https://example.com/atl.png",
    }


def _market():
    return {
        "ready": True,
        "identity": {
            "official_event_id": "401772999",
            "away_team_id": "3",
            "home_team_id": "1",
            "away_abbr": "CHI",
            "home_abbr": "ATL",
        },
    }


def _book():
    return {
        "sportsbook": "FanDuel",
        "away_spread": -1.5,
        "away_price": -105,
        "home_spread": 1.5,
        "home_price": -115,
    }


def _analytics():
    return {
        "ready": True,
        "projected_away_margin": 2.6,
        "away_win_probability": 0.563,
        "home_win_probability": 0.407,
        "away_cover_probability": 0.532,
        "home_cover_probability": 0.468,
        "simulated_away_margin_median": 3.0,
        "parameter_se": 0.7,
        "residual_sd": 12.97,
        "predictive_sd": 13.0,
        "margin_quantiles": {"p05": -19.0, "p25": -6.0, "p50": 3.0, "p75": 11.0, "p95": 24.0},
        "push_probability": 0.0,
        "simulations": 5_000_000,
        "certified_run": True,
        "converged": True,
        "model_quality": "HIGH",
        "away_cover_mc_se": 0.00022,
    }


def test_v7_restores_frozen_team_logos_exact_ids_and_compacts_deep_sections():
    html = render_matchup_card(_game(), _market(), _analytics(), book=_book())

    assert "https://example.com/chi.png" in html
    assert "https://example.com/atl.png" in html
    assert 'data-team-id="3"' in html
    assert 'data-team-id="1"' in html
    assert "ID 3" in html
    assert "ID 1" in html

    # Deep analysis stays available without forcing one giant vertical wall.
    assert html.count("<details") >= 2
    assert "WHY THE MODEL LEANS" in html
    assert "RISK / COUNTERWEIGHTS" in html
    assert "MODEL VERIFICATION" in html


def test_route_hygiene_preserves_cold_deep_link_but_clears_stale_cross_sport_route():
    stale_route_query_keys = _load_hygiene().stale_route_query_keys

    assert stale_route_query_keys(
        {}, {"ks_sport": "NBA", "ks_nba_market": "Spread"}
    ) == ()

    assert stale_route_query_keys(
        {"ks_sport_touch": "NFL", "ks_nfl_market_touch": "Spread"},
        {"ks_sport": "NBA", "ks_nba_market": "Spread"},
    ) == ("ks_nba_market", "ks_sport")


def test_route_hygiene_clears_stale_market_when_user_changes_page_inside_same_sport():
    stale_route_query_keys = _load_hygiene().stale_route_query_keys

    assert stale_route_query_keys(
        {
            "ks_sport_touch": "College Football",
            "ks_cfb_market_touch": "Spread",
        },
        {"ks_sport": "College Football", "ks_cfb_market": "Game Total"},
    ) == ("ks_cfb_market", "ks_sport")

    assert stale_route_query_keys(
        {"ks_sport_touch": "NBA", "ks_nba_market_touch": "Spread"},
        {"ks_sport": "NBA", "ks_nba_market": "Spread"},
    ) == ()


def test_top_overlay_runs_route_hygiene_before_delegating_to_nested_routers():
    source = OVERLAY.read_text(encoding="utf-8")
    assert "from streamlit_route_hygiene_v1 import apply_route_hygiene" in source
    hygiene = "apply_route_hygiene(st.session_state, st.query_params)"
    delegate = "return prior.render_app()"
    assert hygiene in source
    assert source.index(hygiene) < source.index(delegate)
