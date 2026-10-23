from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def _query(href: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(href).query)


def _sample_payload() -> dict:
    return {
        "generated_at_utc": "2026-10-22T23:12:30+00:00",
        "selection_snapshot": {
            "kind": "game-pick",
            "candidate_id": "g1",
            "selected_date": "2026-10-24",
            "away_team": "Duke",
            "home_team": "Virginia",
            "away_record": "5-2",
            "home_record": "6-1",
            "away_logo": "https://www.ncaa.com/duke.svg",
            "home_logo": "https://www.ncaa.com/virginia.svg",
            "market_type": "TOTAL",
            "selection": "Over 46.5",
            "side": "OVER",
            "line": 46.5,
            "sportsbook": "FanDuel",
            "american_odds": -115,
            "probability": .703,
            "market_timestamp": "2026-10-22T23:04:00Z",
            "kickoff_iso": "2026-10-24T19:30:00Z",
        },
        "kyre_verdict": {
            "status": "READY",
            "outcome_confidence": .703,
            "market_implied_probability": .535,
            "market_value_edge": .168,
            "model_fair_price": -237,
            "selected_price": -115,
            "verdict": "BETTABLE EDGE",
        },
        "line_lab": {
            "status": "READY",
            "lab_type": "LINE",
            "scenarios": [
                {"line": 44.5, "over_probability": .76, "model_owner": "Kyre certified CFB total model"},
                {"line": 46.5, "over_probability": .703, "model_owner": "Kyre certified CFB total model"},
                {"line": 48.5, "over_probability": .62, "model_owner": "Kyre certified CFB total model"},
            ],
        },
        "projection": {
            "status": "READY",
            "projected_home_points": 28.6,
            "projected_away_points": 28.7,
            "projected_margin_home": -.1,
            "projected_total": 57.2,
            "selected_probability": .703,
        },
        "drivers": {
            "status": "READY",
            "items": [
                {"title": "Scoring offense", "away": 31.7, "home": 30.0},
                {"title": "Scoring defense", "away": 16.0, "home": 21.1},
                {"title": "Turnover margin / game", "away": .8, "home": 1.2},
            ],
        },
        "recent_form": {
            "status": "READY",
            "items": [
                {"title": "Duke", "value": "4-1 • 31.7 PPG"},
                {"title": "Virginia", "value": "4-1 • 30.0 PPG"},
            ],
        },
        "history": {"status": "SEMANTIC_EMPTY", "reason": "No Previous Meetings"},
        "market_board": {
            "status": "READY",
            "quotes": [
                {"sportsbook": "FanDuel", "side": "OVER", "line": 46.5, "american_odds": -115, "observed_at_utc": "2026-10-22T23:04:00Z"},
                {"sportsbook": "DraftKings", "side": "OVER", "line": 46.5, "american_odds": -110, "observed_at_utc": "2026-10-22T23:03:30Z"},
                {"sportsbook": "BetMGM", "side": "OVER", "line": 46.5, "american_odds": -112, "observed_at_utc": "2026-10-22T23:03:00Z"},
            ],
            "best_available_price": {"sportsbook": "DraftKings", "side": "OVER", "line": 46.5, "american_odds": -110},
        },
        "line_movement": {"status": "SEMANTIC_EMPTY", "reason": "Opening Line Not Independently Verified"},
        "game_environment": {
            "status": "PARTIAL",
            "items": [
                {"title": "Kickoff", "value": "2026-10-24T19:30:00Z"},
                {"title": "Venue", "value": "Scott Stadium"},
            ],
            "reason": "Weather verification pending.",
        },
        "risks": {"status": "READY", "items": [{"title": "Model reliability", "value": .9375}]},
        "flip_conditions": {
            "status": "READY",
            "items": [{"title": "Total threshold", "text": "Recalculate if the verified total moves materially away from 46.5."}],
        },
        "sources": {
            "status": "READY",
            "modules": {"market_board": "READY", "projection": "READY", "history": "SEMANTIC_EMPTY"},
            "gateway": "Kyre Sports API",
        },
    }


def test_v19_identity_market_successor_uses_canonical_route():
    import cfb_top_picks_page_v19 as page

    query = _query(page._page1_handoff({"candidate_id": "g1", "selected_date": "2026-10-24"}, "game-pick"))
    assert query["sport"] == ["cfb"]
    assert query["market"] == ["top-picks"]
    assert query["top_pick_id"] == ["g1"]


def test_v19_renders_team_identity_consensus_best_price_and_edge_breakdown():
    import cfb_top_picks_page_v19 as page

    html = page.render_page2_html(_sample_payload())
    assert page.PAGE_MARKER == "CFB_TOP_PICKS_PAGE2_IDENTITY_MARKET_V3_ACTIVE"
    assert "Duke" in html and "Virginia" in html
    assert 'data-team-logo="away"' in html and 'data-team-logo="home"' in html
    assert 'data-team-logo="away-projection"' in html and 'data-team-logo="home-projection"' in html
    assert 'data-team-logo="away-why"' in html and 'data-team-logo="home-why"' in html
    assert "5-2" in html and "6-1" in html
    assert "SPORTSBOOK CONSENSUS" in html
    assert "BEST PRICE" in html and "DraftKings" in html and "-110" in html
    assert "MODEL 70.3%" in html and "MARKET 53.5%" in html and "EDGE +16.8%" in html
    assert "Opening Line Not Independently Verified" in html
    assert "Duke projected" in html and "Virginia projected" in html
    assert "Model reliability" in html and "93.8%" in html
    assert "PROBABILITY SENSITIVITY" in html


def test_v19_missing_logo_uses_identity_fallback_without_broken_src_or_null_to_zero():
    import cfb_top_picks_page_v19 as page

    payload = _sample_payload()
    payload["selection_snapshot"]["away_logo"] = None
    payload["projection"]["projected_away_points"] = None
    payload["history"] = {"status": "SEMANTIC_EMPTY", "reason": "No Previous Meetings"}
    html = page.render_page2_html(payload)
    assert "<span class=\"v19-fallback\"" in html
    assert 'src=""' not in html
    assert "No Previous Meetings" in html
    assert "<b>Pending verification</b><span>Duke projected</span>" in html
    assert "<b>0.0</b><span>Duke projected</span>" not in html
    assert ">N/A<" not in html
    assert ">Unavailable<" not in html
    assert ">null<" not in html.lower()


def test_v19_missing_sensitivity_probability_never_renders_as_zero_bar():
    import cfb_top_picks_page_v19 as page

    payload = _sample_payload()
    payload["line_lab"]["scenarios"].append({"line": 49.5, "over_probability": None})
    html = page.render_page2_html(payload)
    assert "Line 49.5" in html
    assert "Pending verification" in html
    assert 'data-probability-state="pending"' in html
    assert 'data-probability-state="pending"><b>Line 49.5</b><div class="v19-track"' not in html


def test_v19_has_no_direct_external_data_fetch_path():
    source = Path("cfb_top_picks_page_v19.py").read_text(encoding="utf-8").casefold()
    assert "requests.get" not in source
    assert "urlopen(" not in source
    assert "sportsbook_projection_influence" not in source
    assert "kyre sports api" in source


def test_runtime_v3_is_additive_and_app_activates_it():
    runtime = Path("streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v3.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    assert 'importlib.import_module("cfb_top_picks_page_v19")' in runtime
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v2 as prior" in runtime
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v3" in app
    assert "cfb_top_picks_page_v18.py" not in runtime
