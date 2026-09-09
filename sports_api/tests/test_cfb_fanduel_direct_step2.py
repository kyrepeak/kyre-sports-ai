from datetime import datetime, timezone

import pytest

from sports_api.collectors import cfb_fanduel_direct as collector


def _runner(role, line, odds=-110):
    return {
        "runnerStatus": "ACTIVE",
        "runnerName": role.title(),
        "handicap": line,
        "result": {"type": role},
        "winRunnerOdds": {
            "americanDisplayOdds": {"americanOddsInt": odds}
        },
    }


def _page(*, total=54.5, duplicate_total=False, start="2026-09-12T23:30:00Z"):
    markets = {
        "m1": {
            "marketId": "734.1",
            "eventId": "35990001",
            "marketName": "Total Points",
            "marketStatus": "OPEN",
            "inPlay": False,
            "runners": {
                "over": _runner("OVER", total),
                "under": _runner("UNDER", total),
            },
        }
    }
    if duplicate_total:
        markets["m2"] = {
            "marketId": "734.2",
            "eventId": "35990001",
            "marketName": "Total Points",
            "marketStatus": "OPEN",
            "inPlay": False,
            "runners": {
                "over": _runner("OVER", total),
                "under": _runner("UNDER", total),
            },
        }
    return {
        "attachments": {
            "events": {
                "35990001": {
                    "eventId": "35990001",
                    "name": "Florida A&M @ Miami Florida",
                    "openDate": start,
                },
                "future-1": {
                    "eventId": "future-1",
                    "name": "College Football Team Futures",
                    "openDate": start,
                },
            },
            "markets": markets,
        }
    }


def test_verified_ncaaf_total_page_normalizes_one_game():
    result = collector.normalize_fanduel_ncaaf_page(
        _page(),
        observed_at_utc=datetime(2026, 9, 9, 20, 0, tzinfo=timezone.utc),
    )
    assert result["schema_version"] == "cfb_market_feed_v1"
    assert result["source"].startswith("FanDuel anonymous public NCAAF")
    assert len(result["games"]) == 1
    game = result["games"][0]
    assert game == {
        "game_id": "35990001",
        "home_team": "Miami Florida",
        "away_team": "Florida A&M",
        "start_time_utc": "2026-09-12T23:30:00+00:00",
        "total": 54.5,
        "sportsbook": "FanDuel",
        "updated_at_utc": "2026-09-09T20:00:00+00:00",
        "line_status": "active",
    }
    diag = result["provider_diagnostics"]
    assert diag["network_requests"] == 1
    assert diag["paid_odds_vendor_required"] is False
    assert diag["sportsbook_credentials_required"] is False
    assert diag["wager_actions"] is False


def test_non_matchup_futures_are_never_treated_as_games():
    result = collector.normalize_fanduel_ncaaf_page(
        _page(),
        observed_at_utc=datetime(2026, 9, 9, 20, 0, tzinfo=timezone.utc),
    )
    assert result["provider_diagnostics"]["landing_event_count"] == 2
    assert result["provider_diagnostics"]["matchup_event_count"] == 1
    assert {row["game_id"] for row in result["games"]} == {"35990001"}


def test_duplicate_open_total_markets_fail_closed_per_event():
    with pytest.raises(
        collector.CFBFanDuelCollectorError,
        match="produced no future open Total Points games",
    ):
        collector.normalize_fanduel_ncaaf_page(
            _page(duplicate_total=True),
            observed_at_utc=datetime(2026, 9, 9, 20, 0, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0, 201])
def test_bad_total_lines_never_enter_feed(bad):
    with pytest.raises(collector.CFBFanDuelCollectorError):
        collector.normalize_fanduel_ncaaf_page(
            _page(total=bad),
            observed_at_utc=datetime(2026, 9, 9, 20, 0, tzinfo=timezone.utc),
        )


def test_past_matchups_do_not_enter_current_feed():
    with pytest.raises(collector.CFBFanDuelCollectorError):
        collector.normalize_fanduel_ncaaf_page(
            _page(start="2026-09-08T23:30:00Z"),
            observed_at_utc=datetime(2026, 9, 9, 20, 0, tzinfo=timezone.utc),
        )


def test_collector_supports_injected_network_fetcher():
    called = {"count": 0}

    def fetch():
        called["count"] += 1
        return _page()

    result = collector.collect_fanduel_cfb_total_feed(
        now_utc=datetime(2026, 9, 9, 20, 0, tzinfo=timezone.utc),
        page_fetcher=fetch,
    )
    assert called["count"] == 1
    assert len(result["games"]) == 1
    assert result["market_semantics"]["projection_weight"] == 0.0
