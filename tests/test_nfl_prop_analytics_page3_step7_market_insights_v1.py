from pathlib import Path

import nfl_prop_analytics_page3_market_insights_v1 as step7

STEP7_SRC = Path("nfl_prop_analytics_page3_market_insights_v1.py").read_text()
PAGE_SRC = Path("nfl_prop_analytics_prop_page_v1.py").read_text()


def _games():
    return [
        {"official_event_id": "1", "value": 310.0},
        {"official_event_id": "2", "value": 280.0},
        {"official_event_id": "3", "value": 250.0},
        {"official_event_id": "4", "value": 220.0},
        {"official_event_id": "5", "value": 260.0},
    ]


def test_step7_builds_alternate_analysis_thresholds_without_synthetic_prices():
    lines = step7.build_alternate_lines(260.5, "passing_yards", verified_market_line=262.5)
    assert lines == [250.5, 255.5, 260.5, 262.5, 265.5, 270.5]
    assert step7.ALT_LINES_ARE_SPORTSBOOK_PRICES is False


def test_step7_over_under_history_recalculates_at_selected_line():
    over = step7.historical_side_summary(_games(), line=260.0, side="OVER")
    under = step7.historical_side_summary(_games(), line=260.0, side="UNDER")
    assert over["sample_size"] == 5
    assert over["push_count"] == 1
    assert over["decisive_count"] == 4
    assert over["hit_count"] == 2
    assert over["hit_rate_pct"] == 50.0
    assert under["hit_count"] == 2
    assert under["hit_rate_pct"] == 50.0


def test_step7_pending_gate_stays_locked_and_makes_no_market_request(monkeypatch):
    monkeypatch.setattr(
        step7.passing_market,
        "fetch_event_market",
        lambda event_id: (_ for _ in ()).throw(AssertionError("market request must stay closed")),
    )
    payload = step7.load_verified_market(
        official_event_id="401999001",
        official_athlete_id="3139477",
        market_key="passing_yards",
        gate_open=False,
    )
    assert payload["ready"] is False
    assert payload["state"] == "locked"
    assert payload["projection_weight"] == 0.0


def test_step7_accepts_only_certified_exact_id_market_context(monkeypatch):
    event_market = {
        "ready": True,
        "official_event_id": "401999001",
        "sportsbook": "FanDuel",
        "market_available": True,
        "projection_weight": 0.0,
        "market_context_only": True,
    }
    athlete_market = {
        "ready": True,
        "official_event_id": "401999001",
        "official_athlete_id": "3139477",
        "sportsbook": "FanDuel",
        "line": 264.5,
        "over_odds": -110,
        "under_odds": -110,
        "captured_at_utc": "2026-09-27T00:00:00+00:00",
        "age_seconds": 15.0,
        "projection_weight": 0.0,
        "market_context_only": True,
    }
    monkeypatch.setattr(step7.passing_market, "fetch_event_market", lambda event_id: event_market)
    monkeypatch.setattr(step7.passing_market, "market_for_athlete", lambda event, athlete_id: athlete_market)

    payload = step7.load_verified_market(
        official_event_id="401999001",
        official_athlete_id="3139477",
        market_key="passing_yards",
        gate_open=True,
    )
    assert payload["ready"] is True
    assert payload["state"] == "verified"
    assert payload["line"] == 264.5
    assert payload["over_odds"] == -110
    assert payload["under_odds"] == -110
    assert payload["sportsbook"] == "FanDuel"
    assert payload["projection_weight"] == 0.0


def test_step7_unsupported_prop_fails_closed_without_fabricating_odds():
    payload = step7.load_verified_market(
        official_event_id="401999001",
        official_athlete_id="3139477",
        market_key="interceptions",
        gate_open=True,
    )
    assert payload["ready"] is False
    assert payload["state"] == "unsupported"
    assert "certified exact-ID sportsbook client" in payload["reason"]


def test_step7_insights_are_descriptive_historical_context_only():
    cards = step7.build_insights(
        games=_games(),
        selected_line=260.0,
        side="OVER",
        history_summary={"average": 264.0, "median": 260.0},
    )
    assert cards
    titles = {card["title"] for card in cards}
    assert "THRESHOLD FREQUENCY" in titles
    assert "AVERAGE VS LINE" in titles
    assert "MEDIAN VS LINE" in titles
    assert all("recommend" not in (card["note"] or "").lower() for card in cards)


def test_step7_contract_has_agreed_market_sections_and_safety():
    for token in (
        'PAGE3_MARKET_INSIGHTS_STEP = 7',
        'PAGE3_MARKET_INSIGHTS_VERSION = "v1"',
        'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
        'PROJECTION_LOGIC = False',
        'PROBABILITY_LOGIC = False',
        'RECOMMENDATION_LOGIC = False',
        'STAKE_SIZING_ENABLED = False',
        'WAGER_ACTIONS = False',
        'LIVE_ANALYTICS_REQUIRES_AVAILABLE = True',
        'options=["OVER", "UNDER"]',
        '"STATISTICS", "SUPPORTING STATS", "INSIGHTS", "KEY NOTES"',
        'data-prop-page3-step7-market-insights="',
        'data-prop-page3-step7-odds-state="',
        'data-prop-page3-step7-recommendations="0"',
        'data-prop-page3-step7-wager-actions="0"',
        'Alternate lines are analysis thresholds only',
    ):
        assert token in STEP7_SRC, token


def test_prop_page_wires_step7_after_step6_and_returns_state():
    for token in (
        'from nfl_prop_analytics_page3_market_insights_v1 import (',
        'render_market_insights(',
        'official_event_id=handoff["event_id"]',
        'official_athlete_id=handoff["player_id"]',
        'gate_open=gate_open',
        '"market_insights": market_insights',
    ):
        assert token in PAGE_SRC, token
    assert PAGE_SRC.index("render_supporting_stats(") < PAGE_SRC.index("render_market_insights(")
