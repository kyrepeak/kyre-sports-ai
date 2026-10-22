from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def _query(href: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(href).query)


def test_page1_handoff_uses_canonical_runtime_route_not_legacy_only():
    import cfb_top_picks_page_v18 as page

    href = page._page1_handoff(
        {"candidate_id": "g1", "selected_date": "2026-10-22"},
        "game-pick",
    )
    query = _query(href)
    assert query["sport"] == ["cfb"]
    assert query["market"] == ["top-picks"]
    assert query["top_pick_id"] == ["g1"]
    assert query["top_pick_kind"] == ["game-pick"]
    assert query["top_pick_date"] == ["2026-10-22"]


def test_canonical_handoff_overrides_stale_mlb_runtime_state():
    import cfb_top_picks_page_v18 as page
    from universal_runtime_v5_state import RuntimeRoute, RuntimeState, commit_intent
    from universal_sports_nav_controller_v1 import RouteIntent
    from universal_sports_nav_url_v1 import parse_canonical_query

    href = page._page1_handoff(
        {"candidate_id": "g1", "selected_date": "2026-10-22"},
        "game-pick",
    )
    raw = {key: values[-1] for key, values in _query(href).items()}
    parsed = parse_canonical_query(raw)
    stale = RuntimeState(
        active=RuntimeRoute("mlb", "moneyline", {}, 7, "tap"),
        last_route_by_sport={"mlb": RuntimeRoute("mlb", "moneyline", {}, 7, "tap")},
        generation=7,
    )
    updated = commit_intent(
        stale,
        RouteIntent(parsed.sport_id, parsed.market_id, "canonical_url"),
        parsed.page_params,
    )
    assert (updated.active.sport_id, updated.active.market_id) == ("cfb", "top-picks")


def test_back_link_stays_canonical_cfb_top_picks_and_drops_detail_identity():
    import cfb_top_picks_page_v18 as page

    query = _query(page._back_href({"selected_date": "2026-10-22"}))
    assert query["sport"] == ["cfb"]
    assert query["market"] == ["top-picks"]
    assert query["top_pick_date"] == ["2026-10-22"]
    assert "top_pick_id" not in query


def _sample_payload() -> dict:
    return {
        "selection_snapshot": {
            "kind": "game-pick",
            "candidate_id": "g1",
            "selected_date": "2026-10-22",
            "away_team": "East Carolina",
            "home_team": "Memphis",
            "market_type": "MONEYLINE",
            "selection": "Memphis ML",
            "sportsbook": "FanDuel",
            "american_odds": -420,
            "probability": .777,
            "market_timestamp": "2026-10-22T21:58:00Z",
        },
        "kyre_verdict": {
            "status": "READY",
            "outcome_confidence": .777,
            "market_implied_probability": .808,
            "market_value_edge": -.031,
            "model_fair_price": -348,
            "selected_price": -420,
            "verdict": "PASS AT THIS PRICE",
        },
        "line_lab": {
            "status": "READY",
            "lab_type": "PRICE",
            "scenarios": [
                {"american_odds": -420, "implied_probability": .808, "model_probability": .777, "market_value_edge": -.031},
                {"american_odds": -370, "implied_probability": .787, "model_probability": .777, "market_value_edge": -.010},
                {"american_odds": -320, "implied_probability": .762, "model_probability": .777, "market_value_edge": .015},
            ],
        },
        "projection": {
            "status": "READY",
            "projected_home_points": 36.5,
            "projected_away_points": 21.5,
            "projected_margin_home": 15.0,
            "projected_total": 57.9,
            "model_owner": "Kyre certified CFB model",
        },
        "drivers": {
            "status": "READY",
            "items": [
                {"title": "Scoring offense", "away": 23.5, "home": 35.4},
                {"title": "Total offense", "away": 339.2, "home": 511.7},
            ],
        },
        "recent_form": {"status": "SEMANTIC_EMPTY", "semantic_state": "NO_QUALIFYING_GAMES", "reason": "No Qualifying Games"},
        "history": {"status": "SEMANTIC_EMPTY", "semantic_state": "NO_PREVIOUS_MEETINGS", "reason": "No Previous Meetings"},
        "market_board": {
            "status": "READY",
            "quotes": [
                {"sportsbook": "FanDuel", "side": "HOME", "american_odds": -420, "observed_at_utc": "2026-10-22T21:58:00Z", "freshness_status": "CURRENT"}
            ],
        },
        "line_movement": {"status": "SEMANTIC_EMPTY", "semantic_state": "OPENING_LINE_NOT_VERIFIED", "reason": "Opening Line Not Independently Verified"},
        "availability": {"status": "NOT_APPLICABLE", "semantic_state": "NOT_APPLICABLE_TO_GAME_PICK", "reason": "Player availability is not applicable to this game-pick card."},
        "game_environment": {"status": "PARTIAL", "reason": "Verified kickoff; weather enrichment pending."},
        "risks": {"status": "READY", "items": [{"title": "Model reliability", "value": "0.94"}]},
        "flip_conditions": {"status": "READY", "items": [{"title": "Price threshold", "text": "Positive model value begins at -320 in the tested price ladder."}]},
        "sources": {
            "status": "READY",
            "modules": {"kyre_verdict": "READY", "history": "SEMANTIC_EMPTY"},
            "gateway": "Kyre Sports API",
            "null_is_not_zero": True,
        },
    }


def test_page2_v18_is_compact_six_section_decision_command_center():
    import cfb_top_picks_page_v18 as page

    html = page.render_page2_html(_sample_payload())
    for marker in (
        "GAME DECISION",
        "PRICE + MARKET LAB",
        "MODEL PROJECTION",
        "MATCHUP INTELLIGENCE",
        "WHY / RISKS / FLIP CONDITIONS",
        "DATA INTEGRITY",
    ):
        assert marker in html
    assert "<details" in html
    assert "DATA INTEGRITY" in html
    assert "BUY ZONE" in html
    assert "CURRENT" in html
    assert "Opening Line Not Independently Verified" in html
    assert "No Previous Meetings" in html
    assert "62+00:00" not in html
    assert "↑ TOP" not in html


def test_page2_renderer_does_not_turn_missing_values_into_zero_or_generic_blank_labels():
    import cfb_top_picks_page_v18 as page

    payload = _sample_payload()
    payload["projection"]["projected_home_points"] = None
    payload["projection"]["projected_away_points"] = None
    payload["drivers"] = {"status": "SEMANTIC_EMPTY", "semantic_state": "NO_QUALIFYING_GAMES", "reason": "No Qualifying Games"}
    html = page.render_page2_html(payload)
    assert "0.0</" not in html
    assert ">N/A<" not in html
    assert ">Unavailable<" not in html
    assert ">null<" not in html.lower()
    assert "No Qualifying Games" in html


def test_page2_api_source_path_is_gateway_owned_and_has_no_forbidden_direct_provider_path():
    source = Path("sports_api/api/cfb_top_picks_page2_v1.py").read_text(encoding="utf-8").casefold()
    assert "sportsgameodds" not in source
    assert "espn.com" not in source
    assert "site.api.espn" not in source
    assert "import espn" not in source
    assert "from espn" not in source
    assert "kyre sports api" in source


def test_semantic_empty_states_are_specific_not_generic():
    import sports_api.api.cfb_top_picks_page2_v1 as api

    history = api._semantic("NO_PREVIOUS_MEETINGS", "No Previous Meetings")
    movement = api._semantic("OPENING_LINE_NOT_VERIFIED", "Opening Line Not Independently Verified")
    assert history["status"] == "SEMANTIC_EMPTY"
    assert history["semantic_state"] == "NO_PREVIOUS_MEETINGS"
    assert movement["semantic_state"] == "OPENING_LINE_NOT_VERIFIED"
    assert "DATA_UNAVAILABLE" not in history["reason"]


def test_moneyline_flip_condition_is_derived_from_model_price_lab_not_guessed():
    import sports_api.api.cfb_top_picks_page2_v1 as api

    lab = {
        "status": "READY",
        "lab_type": "PRICE",
        "scenarios": [
            {"american_odds": -420, "market_value_edge": -.031},
            {"american_odds": -370, "market_value_edge": -.010},
            {"american_odds": -320, "market_value_edge": .015},
        ],
    }
    item = api._moneyline_price_flip(lab)
    assert item["title"] == "Price threshold"
    assert "-320" in item["text"]
    assert "positive" in item["text"].casefold()
