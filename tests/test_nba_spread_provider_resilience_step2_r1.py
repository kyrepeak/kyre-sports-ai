from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

try:
    import requests  # type: ignore
except ModuleNotFoundError:
    requests = types.ModuleType("requests")

    class _HTTPError(Exception):
        pass

    class _Session:
        def get(self, *args, **kwargs):
            raise RuntimeError("requests.Session is unavailable in the Runless proof sandbox")

    requests.HTTPError = _HTTPError
    requests.Session = _Session
    sys.modules["requests"] = requests


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
WINDOW = ("2026-10-15",)


def _module():
    return importlib.import_module("nba_spread_schedule_provider_resilience_step2_r1")


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _row(source: str, *, away: str = "BOS", home: str = "NYK", tip: str = "2026-10-15T23:30:00Z") -> dict:
    return {
        "source": source,
        "source_game_id": f"{source}-1",
        "game_key": f"{away}@{home}:2026-10-15",
        "away_tricode": away,
        "away_name": away,
        "home_tricode": home,
        "home_name": home,
        "tip_utc": tip,
        "tip_iso_phoenix": "2026-10-15T16:30:00-07:00",
        "tip_phoenix": "4:30 PM MST",
        "game_date_phoenix": "2026-10-15",
        "status": "UPCOMING",
        "venue": "",
    }


def test_cbs_valid_card_normalizes_to_canonical_schedule_row_and_phoenix_time():
    module = _module()
    result = module.parse_cbs_scoreboard_html(
        _fixture("nba_cbs_scoreboard_step2_valid.html"),
        requested_date="20261015",
    )

    assert result["parse_errors"] == []
    assert result["unknown_identities"] == []
    assert result["missing_times"] == []
    assert len(result["games"]) == 1
    game = result["games"][0]
    assert game["source"] == "CBS Sports"
    assert game["source_game_id"] == "cbs-001"
    assert game["away_tricode"] == "BOS"
    assert game["home_tricode"] == "NYK"
    assert game["game_key"] == "BOS@NYK:2026-10-15"
    assert game["tip_utc"] == "2026-10-15T23:30:00Z"
    assert game["tip_iso_phoenix"].startswith("2026-10-15T16:30:00-07:00")
    assert game["game_date_phoenix"] == "2026-10-15"
    assert game["venue"] == "Madison Square Garden"


def test_cbs_global_nav_and_related_team_links_are_not_parsed_as_games():
    module = _module()
    result = module.parse_cbs_scoreboard_html(
        _fixture("nba_cbs_scoreboard_step2_nav_and_two_games.html"),
        requested_date="20261015",
    )
    assert [game["game_key"] for game in result["games"]] == [
        "GSW@LAL:2026-10-15",
        "NOP@SAS:2026-10-15",
    ]


def test_cbs_two_scoreboard_games_on_one_page_are_both_parsed():
    module = _module()
    result = module.parse_cbs_scoreboard_html(
        _fixture("nba_cbs_scoreboard_step2_nav_and_two_games.html"),
        requested_date="20261015",
    )
    assert len(result["games"]) == 2
    assert {game["source_game_id"] for game in result["games"]} == {"cbs-101", "cbs-102"}


def test_cbs_malformed_unknown_and_missing_time_cards_fail_closed():
    module = _module()
    result = module.parse_cbs_scoreboard_html(
        _fixture("nba_cbs_scoreboard_step2_malformed.html"),
        requested_date="20261015",
    )
    assert result["games"] == []
    assert "XYZ" in result["unknown_identities"]
    assert "bad-missing-time" in result["missing_times"]
    assert "bad-one-team" in result["parse_errors"]


def test_cbs_alias_table_is_explicit_and_no_unknown_team_is_guessed():
    module = _module()
    expected = {
        "NY": "NYK",
        "SA": "SAS",
        "WSH": "WAS",
        "NO": "NOP",
        "GS": "GSW",
        "UTAH": "UTA",
        "PHO": "PHX",
    }
    for cbs_code, canonical in expected.items():
        assert module.CBS_TO_NBA_TRICODE[cbs_code] == canonical
        assert module.normalize_cbs_team_code(cbs_code) == canonical
    assert module.normalize_cbs_team_code("XYZ") is None


def test_official_plus_espn_pair_is_verified():
    module = _module()
    result = module.reconcile_resilient_schedule(
        {
            "NBA Official": [_row("NBA Official")],
            "ESPN NBA": [_row("ESPN NBA")],
            "CBS Sports": [],
        },
        WINDOW,
    )
    assert result["verification"] == "VERIFIED"
    assert result["diagnostic_state"] == "SOURCE_CONSENSUS"
    assert result["source_agreement"] == 2
    assert result["games"][0]["confirming_sources"] == ["NBA Official", "ESPN NBA"]


def test_official_plus_cbs_pair_is_verified():
    module = _module()
    result = module.reconcile_resilient_schedule(
        {
            "NBA Official": [_row("NBA Official")],
            "ESPN NBA": [],
            "CBS Sports": [_row("CBS Sports")],
        },
        WINDOW,
    )
    assert result["verification"] == "VERIFIED"
    assert result["source_agreement"] == 2
    assert result["games"][0]["confirming_sources"] == ["NBA Official", "CBS Sports"]


def test_espn_plus_cbs_pair_is_verified():
    module = _module()
    result = module.reconcile_resilient_schedule(
        {
            "NBA Official": [],
            "ESPN NBA": [_row("ESPN NBA")],
            "CBS Sports": [_row("CBS Sports")],
        },
        WINDOW,
    )
    assert result["verification"] == "VERIFIED"
    assert result["source_agreement"] == 2
    assert result["games"][0]["confirming_sources"] == ["ESPN NBA", "CBS Sports"]


def test_cbs_only_is_unavailable():
    module = _module()
    result = module.reconcile_resilient_schedule(
        {
            "NBA Official": [],
            "ESPN NBA": [],
            "CBS Sports": [_row("CBS Sports")],
        },
        WINDOW,
    )
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "INSUFFICIENT_PROVIDER_QUORUM"
    assert result["games"] == []
    assert result["source_agreement"] == 0


def test_all_three_disagree_fails_closed_as_provider_conflict():
    module = _module()
    result = module.reconcile_resilient_schedule(
        {
            "NBA Official": [_row("NBA Official", tip="2026-10-15T23:30:00Z")],
            "ESPN NBA": [_row("ESPN NBA", tip="2026-10-16T00:10:00Z")],
            "CBS Sports": [_row("CBS Sports", tip="2026-10-16T00:50:00Z")],
        },
        WINDOW,
    )
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "PROVIDER_CONFLICT"
    assert result["games"] == []


def test_two_agreeing_providers_can_certify_when_third_disagrees():
    module = _module()
    result = module.reconcile_resilient_schedule(
        {
            "NBA Official": [_row("NBA Official", tip="2026-10-15T23:30:00Z")],
            "ESPN NBA": [_row("ESPN NBA", tip="2026-10-15T23:35:00Z")],
            "CBS Sports": [_row("CBS Sports", tip="2026-10-16T01:00:00Z")],
        },
        WINDOW,
    )
    assert result["verification"] == "VERIFIED"
    assert result["games"][0]["confirming_sources"] == ["NBA Official", "ESPN NBA"]
    assert result["games"][0]["rejected_sources"] == ["CBS Sports"]


def test_one_provider_unreachable_remaining_two_agree_is_verified():
    module = _module()
    result = module.reconcile_resilient_schedule(
        {
            "NBA Official": [],
            "ESPN NBA": [_row("ESPN NBA")],
            "CBS Sports": [_row("CBS Sports")],
        },
        WINDOW,
        provider_errors={"NBA Official": "TimeoutError"},
    )
    assert result["verification"] == "VERIFIED"
    assert result["provider_errors"] == {"NBA Official": "TimeoutError"}
    assert result["games"][0]["confirming_sources"] == ["ESPN NBA", "CBS Sports"]


def test_tip_time_tolerance_remains_fifteen_minutes():
    module = _module()
    within = module.reconcile_resilient_schedule(
        {
            "NBA Official": [_row("NBA Official", tip="2026-10-15T23:30:00Z")],
            "ESPN NBA": [_row("ESPN NBA", tip="2026-10-15T23:45:00Z")],
            "CBS Sports": [],
        },
        WINDOW,
    )
    outside = module.reconcile_resilient_schedule(
        {
            "NBA Official": [_row("NBA Official", tip="2026-10-15T23:30:00Z")],
            "ESPN NBA": [_row("ESPN NBA", tip="2026-10-15T23:46:00Z")],
            "CBS Sports": [],
        },
        WINDOW,
    )
    assert within["verification"] == "VERIFIED"
    assert outside["verification"] == "UNAVAILABLE"
    assert outside["diagnostic_state"] == "PROVIDER_CONFLICT"


def test_step2_does_not_mutate_frozen_step1_or_production_router_contract():
    module = _module()
    assert module.MAY_MODIFY_STEP1 is False
    assert module.MAY_MODIFY_PRODUCTION_ROUTER is False
    assert module.MAY_MODIFY_MODEL is False
    assert module.MAY_MODIFY_PROJECTION is False
    assert module.MAY_MODIFY_PROBABILITY is False
    assert module.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert module.SCHEDULE_PROVIDERS == ("NBA Official", "ESPN NBA", "CBS Sports")
