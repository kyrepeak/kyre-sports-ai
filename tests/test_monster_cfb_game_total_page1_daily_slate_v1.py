from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKET_PATH = ROOT / "cfb_game_total_page1_daily_slate_market_v1.py"
PAGE_PATH = ROOT / "cfb_game_total_page1_daily_slate_v1.py"
ROUTER_PATH = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1.py"
OUTER_PATH = ROOT / "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py"


def _market():
    assert MARKET_PATH.exists(), "Page 1 market-consensus owner is not implemented yet"
    import cfb_game_total_page1_daily_slate_market_v1 as mod

    return mod


def _page():
    assert PAGE_PATH.exists(), "Canonical Daily Slate Page 1 owner is not implemented yet"
    import cfb_game_total_page1_daily_slate_v1 as mod

    return mod


def _obs(
    *,
    game_id: str = "g1",
    book: str = "Book A",
    provider: str | None = None,
    market: str = "game_total",
    phase: str = "pregame",
    value: float = 55.5,
    timestamp: str = "2026-10-17T16:00:00+00:00",
    transport: str = "source_a",
    identity_verified: bool = True,
    side: str | None = None,
) -> dict:
    row = {
        "game_id": game_id,
        "sportsbook": book,
        "provider_id": provider or book.casefold().replace(" ", "_"),
        "market_type": market,
        "phase": phase,
        "value": value,
        "observed_at_utc": timestamp,
        "transport": transport,
        "identity_verified": identity_verified,
        "fabrication": False,
    }
    if side is not None:
        row["side"] = side
    return row


def _game(
    event_id: str,
    kickoff: str,
    *,
    status: str = "Scheduled",
    away: str = "Away",
    home: str = "Home",
    subdivisions: tuple[str, ...] = ("FBS",),
    conference: str = "Big 12",
    ranked: bool = False,
) -> dict:
    return {
        "event_id": event_id,
        "kickoff_phoenix": kickoff,
        "phoenix_date": kickoff[:10],
        "away": {
            "name": away,
            "logo": "https://example.test/away.png",
            "record": "5-1",
            "rank": 12 if ranked else None,
            "conference": conference,
            "score": "17" if status in {"Live", "Halftime", "Final"} else None,
        },
        "home": {
            "name": home,
            "logo": "https://example.test/home.png",
            "record": "4-2",
            "rank": None,
            "conference": conference,
            "score": "14" if status in {"Live", "Halftime", "Final"} else None,
        },
        "subdivisions": list(subdivisions),
        "venue": "Example Stadium",
        "city": "Tempe, AZ",
        "broadcast": "ESPN",
        "weather": {"summary": "Clear", "temperature_f": 82, "wind_mph": 8},
        "status": {"state": status, "detail": status, "period": 3 if status == "Live" else None, "clock": "07:42" if status == "Live" else None},
        "market_observations": [_obs(game_id=event_id)],
        "identity_verified": True,
        "fabrication": False,
    }


# --------------------------- Task 2 market contract ---------------------------


def test_market_owner_does_not_exist_before_implementation() -> None:
    assert MARKET_PATH.exists(), "market owner intentionally missing at RED"


def test_normalization_rejects_unverified_or_wrong_identity() -> None:
    mod = _market()
    assert mod.normalize_market_observation(_obs(identity_verified=False)) is None
    assert mod.normalize_market_observation({**_obs(), "game_id": ""}) is None


def test_duplicate_same_book_across_transports_counts_once() -> None:
    mod = _market()
    rows = [
        _obs(book="FanDuel", transport="espn", timestamp="2026-10-17T15:59:00+00:00", value=56.0),
        _obs(book="FanDuel", transport="kyre", timestamp="2026-10-17T16:00:00+00:00", value=56.0),
    ]
    result = mod.select_observed_consensus(rows, tolerance=0.5)
    assert result["status"] == "VERIFIED"
    assert result["confidence"] == "Limited coverage"
    assert result["independent_source_count"] == 1
    assert result["selected_quote"]["transport"] == "kyre"


def test_consensus_selects_actual_observed_quote_nearest_median() -> None:
    mod = _market()
    rows = [_obs(book="A", value=54.5), _obs(book="B", value=55.5), _obs(book="C", value=57.0)]
    result = mod.select_observed_consensus(rows, tolerance=0.5)
    assert result["selected_quote"]["value"] == 55.5
    assert result["selected_quote"] in [mod.normalize_market_observation(row) for row in rows]
    assert result["synthetic_value"] is False


def test_consensus_tie_prefers_freshest_then_stable_provider_id() -> None:
    mod = _market()
    rows = [
        _obs(book="A", provider="provider_a", value=55.0, timestamp="2026-10-17T15:00:00+00:00"),
        _obs(book="B", provider="provider_b", value=56.0, timestamp="2026-10-17T16:00:00+00:00"),
    ]
    result = mod.select_observed_consensus(rows, tolerance=1.0)
    assert result["selected_quote"]["provider_id"] == "provider_b"

    same_time = [
        _obs(book="A", provider="provider_a", value=55.0),
        _obs(book="B", provider="provider_b", value=56.0),
    ]
    result = mod.select_observed_consensus(same_time, tolerance=1.0)
    assert result["selected_quote"]["provider_id"] == "provider_a"


def test_confidence_strong_mixed_limited_and_unavailable() -> None:
    mod = _market()
    strong = mod.select_observed_consensus([_obs(book="A", value=55.0), _obs(book="B", value=55.5)], tolerance=0.5)
    assert strong["confidence"] == "Strong consensus"
    mixed = mod.select_observed_consensus([_obs(book="A", value=54.0), _obs(book="B", value=56.0)], tolerance=0.5)
    assert mixed["confidence"] == "Mixed market"
    limited = mod.select_observed_consensus([_obs(book="A", value=55.0)], tolerance=0.5)
    assert limited["confidence"] == "Limited coverage"
    unavailable = mod.select_observed_consensus([], tolerance=0.5)
    assert unavailable["status"] == "UNAVAILABLE"
    assert unavailable["confidence"] == "Unavailable"


def test_opening_pregame_and_live_market_states_remain_separate() -> None:
    mod = _market()
    rows = [
        _obs(book="A", phase="opening", value=52.5, timestamp="2026-10-15T12:00:00+00:00"),
        _obs(book="A", phase="pregame", value=54.5, timestamp="2026-10-17T15:00:00+00:00"),
        _obs(book="A", phase="live", value=61.5, timestamp="2026-10-17T20:00:00+00:00"),
    ]
    context = mod.build_game_market_context("g1", rows)
    assert context["opening"]["game_total"]["selected_quote"]["value"] == 52.5
    assert context["pregame"]["game_total"]["selected_quote"]["value"] == 54.5
    assert context["live"]["game_total"]["selected_quote"]["value"] == 61.5
    assert context["current"]["game_total"]["selected_quote"]["value"] == 54.5


def test_market_specific_tolerances_are_pinned() -> None:
    mod = _market()
    assert mod.SPREAD_TOLERANCE == 0.5
    assert mod.GAME_TOTAL_TOLERANCE == 0.5
    assert mod.MONEYLINE_TOLERANCE == 15.0
    assert mod.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_moneyline_same_side_is_required_for_consensus() -> None:
    mod = _market()
    rows = [
        _obs(book="A", market="moneyline", side="home", value=-130),
        _obs(book="B", market="moneyline", side="away", value=120),
    ]
    context = mod.build_game_market_context("g1", rows)
    assert context["pregame"]["moneyline_home"]["independent_source_count"] == 1
    assert context["pregame"]["moneyline_away"]["independent_source_count"] == 1
    assert context["pregame"]["moneyline_home"]["confidence"] == "Limited coverage"
    assert context["pregame"]["moneyline_away"]["confidence"] == "Limited coverage"


# ---------------------------- Task 3 Page 1 contract ---------------------------


def test_page1_owner_exists_and_pins_approved_constants() -> None:
    mod = _page()
    assert mod.MAX_FORWARD_SEARCH_DAYS == 21
    assert mod.DEFAULT_FILTER == "All Games"
    assert mod.FILTER_OPTIONS == ("All Games", "Live", "Upcoming", "Ranked", "FBS", "FCS", "Conference")
    assert mod.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_empty_requested_day_auto_advances_to_next_game_date_with_bound() -> None:
    mod = _page()
    calls: list[date] = []

    def loader(day: date):
        calls.append(day)
        if day == date(2026, 10, 19):
            return {"game_count": 1, "games": [_game("next", "2026-10-19T12:00:00-07:00")]}
        return {"game_count": 0, "games": []}

    effective, payload = mod.resolve_effective_slate_date(date(2026, 10, 17), loader)
    assert effective == date(2026, 10, 19)
    assert payload["game_count"] == 1
    assert calls == [date(2026, 10, 17), date(2026, 10, 18), date(2026, 10, 19)]

    effective, payload = mod.resolve_effective_slate_date(
        date(2026, 10, 17), lambda _day: {"game_count": 0, "games": []}, max_forward_days=2
    )
    assert effective == date(2026, 10, 17)
    assert payload["game_count"] == 0
    assert payload["auto_advance_exhausted"] is True


def test_filters_and_search_only_change_visible_games() -> None:
    mod = _page()
    games = [
        _game("live", "2026-10-17T11:00:00-07:00", status="Live", away="Arizona State", home="Texas Tech", ranked=True),
        _game("fcs", "2026-10-17T13:00:00-07:00", subdivisions=("FCS",), conference="Big Sky", away="Montana", home="Idaho"),
        _game("cross", "2026-10-17T15:00:00-07:00", subdivisions=("FBS", "FCS"), away="FCS School", home="FBS School"),
        _game("final", "2026-10-17T09:00:00-07:00", status="Final", away="Old", home="Done"),
    ]
    assert len(mod.filter_slate_games(games)) == 4
    assert [g["event_id"] for g in mod.filter_slate_games(games, filter_name="Live")] == ["live"]
    assert {g["event_id"] for g in mod.filter_slate_games(games, filter_name="Upcoming")} == {"fcs", "cross"}
    assert [g["event_id"] for g in mod.filter_slate_games(games, filter_name="Ranked")] == ["live"]
    assert {g["event_id"] for g in mod.filter_slate_games(games, filter_name="FBS")} == {"live", "cross", "final"}
    assert {g["event_id"] for g in mod.filter_slate_games(games, filter_name="FCS")} == {"fcs", "cross"}
    assert [g["event_id"] for g in mod.filter_slate_games(games, filter_name="Conference", conference="Big Sky")] == ["fcs"]
    assert [g["event_id"] for g in mod.filter_slate_games(games, search="mont")] == ["fcs"]
    assert [g["event_id"] for g in mod.filter_slate_games(games, search="texas tech")] == ["live"]


def test_cross_division_game_is_once_in_all_but_in_both_subdivision_filters() -> None:
    mod = _page()
    cross = _game("cross", "2026-10-17T15:00:00-07:00", subdivisions=("FBS", "FCS"))
    games = [cross]
    assert len(mod.filter_slate_games(games, filter_name="All Games")) == 1
    assert len(mod.filter_slate_games(games, filter_name="FBS")) == 1
    assert len(mod.filter_slate_games(games, filter_name="FCS")) == 1


def test_kickoff_windows_and_groups_are_chronological_with_live_first_completed_last() -> None:
    mod = _page()
    assert mod.kickoff_window(_game("a", "2026-10-17T11:59:00-07:00")) == "Early"
    assert mod.kickoff_window(_game("b", "2026-10-17T12:00:00-07:00")) == "Afternoon"
    assert mod.kickoff_window(_game("c", "2026-10-17T17:00:00-07:00")) == "Evening"
    assert mod.kickoff_window(_game("d", "2026-10-17T21:00:00-07:00")) == "Late"

    games = [
        _game("late", "2026-10-17T21:30:00-07:00"),
        _game("live", "2026-10-17T13:00:00-07:00", status="Live"),
        _game("early2", "2026-10-17T11:30:00-07:00"),
        _game("early1", "2026-10-17T10:30:00-07:00"),
        _game("final", "2026-10-17T09:00:00-07:00", status="Final"),
    ]
    groups = mod.group_slate_games(games, now_phoenix=datetime.fromisoformat("2026-10-17T10:00:00-07:00"))
    assert list(groups) == ["Live Games", "Early Games", "Afternoon Games", "Evening Games", "Late Games", "Completed Games"]
    assert [g["event_id"] for g in groups["Live Games"]] == ["live"]
    assert [g["event_id"] for g in groups["Early Games"]] == ["early1", "early2"]
    assert [g["event_id"] for g in groups["Completed Games"]] == ["final"]
    assert mod.next_upcoming_window(groups) == "Early Games"


def test_missing_card_fields_remain_truthful_and_availability_requires_verified_observation() -> None:
    mod = _page()
    game = _game("missing", "2026-10-17T14:00:00-07:00")
    game["broadcast"] = None
    game["weather"] = None
    game["venue"] = None
    game["market_observations"] = []
    card = mod.card_view_model(game)
    assert card["broadcast"] == "—"
    assert card["weather"] == "—"
    assert card["venue"] == "Unavailable"
    assert card["moneyline"] == "Unavailable"
    assert card["spread"] == "Unavailable"
    assert card["total"] == "Unavailable"
    assert card["availability"] == "Unavailable"

    game["availability"] = {"verified": True, "summary": "QB questionable"}
    assert mod.card_view_model(game)["availability"] == "QB questionable"


def test_view_game_href_is_the_explicit_selected_event_handoff() -> None:
    mod = _page()
    href = mod.view_game_href(_game("401999999", "2026-10-17T14:00:00-07:00"), date(2026, 10, 17))
    assert "ks_sport=College+Football" in href
    assert "ks_cfb_market=Game+Total" in href
    assert "ks_cfb_game_total_date=2026-10-17" in href
    assert "ks_cfb_game_total_event_id=401999999" in href
    assert "ks_cfb_game_total_selector_sync=401999999" in href


def test_page1_source_is_mobile_first_compact_expandable_and_contains_no_deep_analysis_wall() -> None:
    assert PAGE_PATH.exists(), "Page 1 owner missing at RED"
    source = PAGE_PATH.read_text(encoding="utf-8")
    for text in (
        "CFB Game Total",
        "Phoenix Time",
        "All Games",
        "Live",
        "Upcoming",
        "Ranked",
        "FBS",
        "FCS",
        "Conference",
        "More ↓",
        "View Game →",
        "Completed Games",
        "No upcoming games found",
    ):
        assert text in source
    assert "@media(max-width:640px)" in source.replace(" ", "")
    assert "grid-template-columns:1fr auto 1fr" not in source.replace(" ", "")
    lowered = source.casefold()
    for forbidden in (
        "projected final score",
        "projected game total",
        "red-zone analysis",
        "explosive-play analysis",
        "market-aware football reasoning",
        "betting recommendation",
    ):
        assert forbidden not in lowered
