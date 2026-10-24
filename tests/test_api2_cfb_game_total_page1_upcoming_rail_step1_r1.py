from __future__ import annotations

from datetime import date, datetime, timezone
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = importlib.import_module("sports_api.api.cfb_game_total_page1_v1")
NOW = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)


def _game(game_id: str, kickoff_iso: str | None, *, status: str | None = None) -> dict:
    row = {
        "game_id": game_id,
        "identity_key": game_id,
        "identity_verified": True,
        "date_matches_query": True,
        "away_team": f"Away {game_id}",
        "home_team": f"Home {game_id}",
        "kickoff_iso": kickoff_iso,
    }
    if status is not None:
        row["status"] = status
    return row


def test_upcoming_predicate_rejects_started_and_terminal_games():
    is_upcoming = API._is_upcoming_game

    assert is_upcoming(_game("future", "2026-10-24T18:00:00+00:00", status="scheduled"), NOW) is True
    assert is_upcoming(_game("at-kickoff", "2026-10-24T17:00:00+00:00", status="scheduled"), NOW) is False
    assert is_upcoming(_game("past-stale", "2026-10-24T16:59:59+00:00", status="scheduled"), NOW) is False
    assert is_upcoming(_game("live-no-time", None, status="in progress"), NOW) is False
    assert is_upcoming(_game("final-no-time", None, status="final"), NOW) is False
    assert is_upcoming(_game("complete-no-time", None, status="completed"), NOW) is False
    assert is_upcoming(_game("future-no-time", None, status="pregame"), NOW) is True


def test_explicit_date_filters_dead_games_before_market_routing(monkeypatch):
    past = _game("past", "2026-10-24T16:00:00+00:00", status="scheduled")
    live = _game("live", None, status="live")
    future = _game("future", "2026-10-24T18:00:00+00:00", status="scheduled")
    routed: dict[str, list[str]] = {}

    monkeypatch.setattr(API, "_load_ncaa_games", lambda day: [past, live, future])

    def market_state(games):
        routed["market"] = [row["game_id"] for row in games]
        return {}, []

    def consensus_state(games):
        routed["consensus"] = [row["game_id"] for row in games]
        return {}, []

    monkeypatch.setattr(API, "_market_state", market_state)
    monkeypatch.setattr(API, "collect_consensus_market_rows", consensus_state)

    payload = API.build_page1_payload(
        game_date="2026-10-24",
        now_provider=lambda: NOW,
    )

    assert [row["game_id"] for row in payload["games"]] == ["future"]
    assert routed == {"market": ["future"], "consensus": ["future"]}
    assert payload["summary"]["games"] == 1


def test_v4_horizontal_rail_contract_and_page1_selection():
    page = ROOT / "cfb_game_total_page1_atier_v4.py"
    assert page.exists(), "V4 upcoming-rail successor has not been implemented yet"

    module = importlib.import_module("cfb_game_total_page1_atier_v4")
    future_a = _game("a", "2026-10-24T18:00:00+00:00")
    future_b = _game("b", "2026-10-24T19:00:00+00:00")

    assert module._select_game([future_a, future_b], "") == future_a
    assert module._select_game([future_a, future_b], "b") == future_b

    href = module._rail_href(future_b, date(2026, 10, 24))
    assert "cfbgt_game=b" in href
    assert "sport=cfb" in href
    assert "market=game-total" in href
    assert "game_id=" not in href
    assert "ks_cfb_game_total_event_id" not in href

    source = page.read_text(encoding="utf-8")
    compact = "".join(source.split()).casefold()
    assert "overflow-x:auto" in compact
    assert "white-space:nowrap" in compact
    assert "o/u" in source.casefold()
    assert "_render_card(selected,1,selected_day)" in compact


def test_v5_successor_preserves_v4_boundaries_without_page2_or_model_mutation():
    wrapper = (ROOT / "cfb_game_total_page1_api_bootstrap_repair_r1.py").read_text(encoding="utf-8")
    assert "cfb_game_total_page1_atier_v6" in wrapper
    assert "cfb_game_total_page1_atier_v4 as atier" not in wrapper

    successor = (ROOT / "cfb_game_total_page1_atier_v5.py").read_text(encoding="utf-8")
    assert "import cfb_game_total_page1_atier_v4 as prior" in successor
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in successor
    assert "MAY_MODIFY_MODEL = False" in successor
    assert "MAY_MODIFY_PROJECTION = False" in successor
    assert "MAY_MODIFY_PROBABILITY = False" in successor
    assert "MAY_MODIFY_RANKING = False" in successor
    assert "MAY_MODIFY_SELECTION = False" in successor
    assert "MAY_MODIFY_SELECTED_GAME_RUNTIME = False" in successor
    folded = successor.casefold()
    assert "sgo" not in folded
    assert "espn" not in folded
    assert "espn bet" not in folded
