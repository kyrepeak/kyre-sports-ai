from __future__ import annotations

import importlib
import sys

import streamlit_memory_lazy_router_v136 as router


LEAKED_SECTION = '<section class="ksp4-team-panel ksp4-away">'
LEAKED_INDENTED_SECTION = '\n    <section class="ksp4-team-panel ksp4-away">'


def _game() -> dict:
    return {
        "game_id": "401000001",
        "state": "pre",
        "season_type": "Regular Season",
        "away_team": "Arizona Cardinals",
        "away_abbr": "ARI",
        "away_record": "1-0",
        "away_logo": "https://example.com/ari.png",
        "home_team": "New Orleans Saints",
        "home_abbr": "NO",
        "home_record": "1-0",
        "home_logo": "https://example.com/no.png",
        "tip_et": "1:00 PM ET",
        "venue": "Caesars Superdome",
        "broadcast": "FOX",
    }


def _market() -> dict:
    return {
        "ready": True,
        "reason": "",
        "projection_weight": 0.0,
        "books": [
            {
                "sportsbook": "FanDuel",
                "away_spread": -2.5,
                "away_price": -110,
                "home_spread": 2.5,
                "home_price": -110,
                "age_seconds": 18,
            }
        ],
    }


def _analytics() -> dict:
    return {
        "ready": True,
        "projected_away_margin": 3.2,
        "parameter_se": 1.15,
        "residual_sd": 12.4,
        "model_quality": "HIGH",
        "certified_run": True,
        "converged": True,
        "simulations": 5_000_000,
        "seed": 20260914,
        "simulated_away_margin_mean": 3.1,
        "simulated_away_margin_median": 3.0,
        "away_cover_probability": 0.548,
        "home_cover_probability": 0.442,
        "push_probability": 0.010,
        "away_win_probability": 0.603,
        "margin_quantiles": {"p25": -4.0, "p75": 10.0},
        "sportsbook_projection_influence": 0.0,
    }


def test_v136_fresh_v4_import_never_leaks_indented_section_markup(monkeypatch) -> None:
    """Regression: a lazy-route purge must not show raw <section ...> text."""
    monkeypatch.delitem(sys.modules, "nfl_spread_hub_v4", raising=False)
    importlib.invalidate_caches()

    fresh_v4 = router._guard_route_import(importlib.import_module, "nfl_spread_hub_v4")
    html = fresh_v4._matchup_card(_game(), _market(), _analytics())

    # This is the exact tag family that visibly leaked when Markdown treated
    # V4's indented multiline HTML as a code block after a lazy-route purge.
    assert LEAKED_SECTION in html
    assert LEAKED_INDENTED_SECTION not in html

    # The certified guard intentionally flattens generated matchup markup so
    # Streamlit receives HTML, not an indented Markdown-code payload.
    assert "\n" not in html
    assert fresh_v4._KSP4_HTML_RENDER_GUARD == "flatten_generated_html"
    assert router.HTML_RENDER_GUARD_SCOPE == "route_purge_reimport_safe"
    assert "Arizona Cardinals" in html
    assert "New Orleans Saints" in html
    assert "5,000,000 simulations" in html
    assert "sportsbook influence on projection math 0.0%" in html
