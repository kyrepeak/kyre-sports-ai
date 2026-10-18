from __future__ import annotations

import inspect

import pytest

import sports_api.wnba_prop_feed_failover as f
from sports_api.collectors.wnba_fanduel_direct import (
    FANDUEL_PROVIDER_ID,
    WNBAFanDuelCollectorError,
)


def _collection(provider_id="fanduel"):
    return {
        "provider_id": provider_id,
        "feed_source": f"{provider_id} test feed",
        "feed_format": "canonical_offers_v1",
        "odds_format": "american",
        "date": "2026-10-19",
        "season": 2026,
        "collected_at_utc": "2026-10-18T18:45:00+00:00",
        "raw_feed": {"offers": [{"sportsbook": "FanDuel"}]},
    }


def _snapshot(events):
    def persist(**kwargs):
        events.append(("persist", kwargs["provider_id"]))
        return {
            "snapshot_id": f"snap-{kwargs['provider_id']}",
            "snapshot_fingerprint_sha256": "a" * 64,
        }
    return persist


def _line_board(events, *, line_count=1):
    def build(raw_feed, **kwargs):
        events.append(("validate", kwargs["feed_source"]))
        return {
            "normalized_line_count": line_count,
            "official_slate_reference": {"playable_game_ids": ["401999001"]},
            "line_board_fingerprint_sha256": "b" * 64,
        }
    return build


def _attempts(**kwargs):
    return {"ok": True}


def _unused(*args, **kwargs):
    raise AssertionError("unexpected provider called")


def test_explicit_fanduel_kyre_order_is_preserved():
    assert f.resolve_failover_order(["fanduel", "kyre"], env={}) == ["fanduel", "kyre"]


def test_collect_candidate_routes_fanduel_to_dedicated_collector():
    calls = []

    def fanduel_collector(**kwargs):
        calls.append((kwargs["date"], kwargs["season"]))
        return _collection("fanduel")

    candidate = f._collect_candidate(
        FANDUEL_PROVIDER_ID,
        date="2026-10-19",
        season=2026,
        env={},
        requester=None,
        generic_collector=_unused,
        sportsgameodds_collector=_unused,
        kyre_market_collector=_unused,
        fanduel_collector=fanduel_collector,
    )

    assert calls == [("2026-10-19", 2026)]
    assert candidate["provider_id"] == "fanduel"
    assert candidate["raw_feed"] == _collection()["raw_feed"]


def test_fanduel_snapshot_persists_before_market_acceptance():
    events = []

    result = f.collect_failover_line_board(
        ["fanduel"],
        date="2026-10-19",
        season=2026,
        require_persistent_store=False,
        env={},
        fanduel_collector=lambda **kwargs: _collection("fanduel"),
        generic_collector=_unused,
        sportsgameodds_collector=_unused,
        kyre_market_collector=_unused,
        line_board_builder=_line_board(events),
        snapshot_persister=_snapshot(events),
        attempt_appender=_attempts,
    )

    assert result["selected_provider_id"] == "fanduel"
    assert events[0] == ("persist", "fanduel")
    assert events[1][0] == "validate"


def test_http_success_with_zero_normalized_lines_is_not_provider_success():
    events = []

    with pytest.raises(f.WNBAPropFeedFailoverNotReadyError):
        f.collect_failover_line_board(
            ["fanduel"],
            date="2026-10-19",
            season=2026,
            minimum_normalized_lines=1,
            require_persistent_store=False,
            env={},
            fanduel_collector=lambda **kwargs: _collection("fanduel"),
            generic_collector=_unused,
            sportsgameodds_collector=_unused,
            kyre_market_collector=_unused,
            line_board_builder=_line_board(events, line_count=0),
            snapshot_persister=_snapshot(events),
            attempt_appender=_attempts,
        )

    assert events[:2] == [("persist", "fanduel"), ("validate", "fanduel test feed")]


def test_fanduel_failure_falls_through_to_kyre_sequentially():
    calls = []
    events = []

    def fanduel_collector(**kwargs):
        calls.append("fanduel")
        raise WNBAFanDuelCollectorError("temporary FanDuel upstream failure")

    def kyre_collector(**kwargs):
        calls.append("kyre")
        return _collection("kyre")

    result = f.collect_failover_line_board(
        ["fanduel", "kyre"],
        date="2026-10-19",
        season=2026,
        require_persistent_store=False,
        env={},
        fanduel_collector=fanduel_collector,
        generic_collector=_unused,
        sportsgameodds_collector=_unused,
        kyre_market_collector=kyre_collector,
        line_board_builder=_line_board(events),
        snapshot_persister=_snapshot(events),
        attempt_appender=_attempts,
    )

    assert calls == ["fanduel", "kyre"]
    assert result["selected_provider_id"] == "kyre"
    assert result["selected_failover_rank"] == 2


def test_public_failover_function_exposes_fanduel_collector_injection():
    assert "fanduel_collector" in inspect.signature(f.collect_failover_line_board).parameters
