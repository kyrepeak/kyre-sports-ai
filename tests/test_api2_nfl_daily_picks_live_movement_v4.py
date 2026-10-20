from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib


NOW = datetime(2026, 10, 20, 2, 30, tzinfo=timezone.utc)


def _module():
    return importlib.import_module("nfl_daily_picks_live_movement_v4")


def _obs(*, market="spread", side="HOME", book="FanDuel", line=-3.0, price=-110, seconds=20, verified=True):
    return {
        "game_id": "g1",
        "market_id": market,
        "side": side,
        "book": book,
        "line": line,
        "price": price,
        "updated_at": NOW - timedelta(seconds=seconds),
        "verified": verified,
        "provider": "Kyre Sports API",
    }


def test_verified_tape_requires_two_distinct_verified_fresh_snapshots() -> None:
    live = _module()
    current = _obs(line=-3.5, seconds=10)
    previous = _obs(line=-3.0, seconds=50)

    move = live.verified_market_movement((previous, current), now_utc=NOW)
    assert move["ready"] is True
    assert move["metric"] == "line"
    assert move["previous_value"] == -3.0
    assert move["current_value"] == -3.5
    assert move["delta"] == -0.5
    assert move["direction"] == "DOWN"
    assert move["book"] == "FanDuel"

    single = live.verified_market_movement((current,), now_utc=NOW)
    assert single["ready"] is False
    assert single["reason"] == "AWAITING_SECOND_VERIFIED_SNAPSHOT"


def test_moneyline_movement_uses_price_not_fake_line() -> None:
    live = _module()
    previous = _obs(market="moneyline", line=None, price=-125, seconds=60)
    current = _obs(market="moneyline", line=None, price=-110, seconds=10)
    move = live.verified_market_movement((previous, current), now_utc=NOW)

    assert move["ready"] is True
    assert move["metric"] == "price"
    assert move["previous_value"] == -125.0
    assert move["current_value"] == -110.0
    assert move["delta"] == 15.0
    assert move["direction"] == "UP"


def test_unverified_stale_or_nonchronological_evidence_fails_closed() -> None:
    live = _module()
    stale = _obs(line=-2.5, seconds=2000)
    current = _obs(line=-3.0, seconds=10)
    assert live.verified_market_movement((stale, current), now_utc=NOW)["ready"] is False

    unverified = _obs(line=-2.5, seconds=50, verified=False)
    assert live.verified_market_movement((unverified, current), now_utc=NOW)["ready"] is False

    duplicate_time = dict(current, line=-2.5)
    same_clock = live.verified_market_movement((duplicate_time, current), now_utc=NOW)
    assert same_clock["ready"] is False
    assert same_clock["reason"] == "AWAITING_SECOND_VERIFIED_SNAPSHOT"


def test_snapshot_history_is_bounded_deduplicated_and_preserves_source_identity() -> None:
    live = _module()
    history = [_obs(line=-2.0 - i * 0.5, seconds=100 - i * 10) for i in range(6)]
    current = [_obs(line=-5.0, seconds=5)]
    merged = live.merge_verified_history(history, current, now_utc=NOW, max_points_per_key=4)

    key_rows = [row for row in merged if row["game_id"] == "g1" and row["book"] == "FanDuel"]
    assert len(key_rows) == 4
    assert key_rows[-1]["line"] == -5.0
    assert all(row["verified"] is True for row in key_rows)
    assert all(row["provider"] == "Kyre Sports API" for row in key_rows)


def test_projection_firewall_is_explicitly_zero() -> None:
    live = _module()
    assert live.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert live.MAY_MODIFY_PROJECTION is False
