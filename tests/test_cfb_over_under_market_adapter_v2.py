from __future__ import annotations

from datetime import datetime, timezone

import cfb_over_under_market_adapter_v2 as adapter


NOW = datetime(2026, 9, 10, 4, 20, 0, tzinfo=timezone.utc)


def _payload(
    *,
    captured_at="2026-09-10T04:19:00+00:00",
    line_updated_at="2026-09-10T04:18:30+00:00",
    game_id="401858213",
    sportsbook="FanDuel",
    line_status="active",
):
    return {
        "step": 3,
        "schema_version": "cfb_odds_v1",
        "captured_at_utc": captured_at,
        "source": "test",
        "game_count": 1,
        "games": [
            {
                "game_id": game_id,
                "game_date": "2026-09-10",
                "away_team": "Florida A&M",
                "home_team": "Miami",
                "sportsbook": sportsbook,
                "market_type": "game_total",
                "total": 62.5,
                "line_status": line_status,
                "line_updated_at_utc": line_updated_at,
                "identity_verified": True,
            }
        ],
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
        "diagnostics": {
            "complete_identity_coverage": True,
            "unmatched_market_rows": 0,
            "synthetic_official_ids": False,
            "fuzzy_matching": False,
        },
    }


def test_step5a_accepts_fresh_fanduel_official_id_payload():
    out = adapter.validate_fresh_payload(
        _payload(),
        requested_sportsbook="FanDuel",
        now_utc=NOW,
    )
    assert out["freshness_status"] == "FRESH"
    assert out["rows_verified"] == 1
    assert out["captured_age_seconds"] == 60.0
    assert out["max_line_age_seconds"] == 90.0
    assert out["sportsbook_identity_verified"] is True
    assert out["official_event_ids_numeric"] is True
    assert out["projection_weight"] == 0.0


def test_step5a_rejects_stale_capture():
    try:
        adapter.validate_fresh_payload(
            _payload(captured_at="2026-09-10T04:10:00+00:00"),
            requested_sportsbook="FanDuel",
            now_utc=NOW,
        )
    except ValueError as exc:
        assert str(exc).startswith("stale_capture:")
    else:
        raise AssertionError("stale capture was accepted")


def test_step5a_rejects_stale_line():
    try:
        adapter.validate_fresh_payload(
            _payload(line_updated_at="2026-09-10T04:10:00+00:00"),
            requested_sportsbook="FanDuel",
            now_utc=NOW,
        )
    except ValueError as exc:
        assert str(exc).startswith("stale_line:401858213:")
    else:
        raise AssertionError("stale line was accepted")


def test_step5a_rejects_material_future_timestamp():
    try:
        adapter.validate_fresh_payload(
            _payload(captured_at="2026-09-10T04:22:00+00:00"),
            requested_sportsbook="FanDuel",
            now_utc=NOW,
        )
    except ValueError as exc:
        assert str(exc) == "unsafe_future_timestamp:captured_at_utc"
    else:
        raise AssertionError("future capture was accepted")


def test_step5a_rejects_wrong_sportsbook_identity():
    try:
        adapter.validate_fresh_payload(
            _payload(sportsbook="DraftKings"),
            requested_sportsbook="FanDuel",
            now_utc=NOW,
        )
    except ValueError as exc:
        assert str(exc) == "unsafe_sportsbook_mismatch:DraftKings"
    else:
        raise AssertionError("wrong sportsbook row was accepted")


def test_step5a_rejects_synthetic_official_game_id():
    try:
        adapter.validate_fresh_payload(
            _payload(game_id="synthetic-401858213"),
            requested_sportsbook="FanDuel",
            now_utc=NOW,
        )
    except ValueError as exc:
        assert str(exc) == "unsafe_non_official_event_id"
    else:
        raise AssertionError("synthetic official game ID was accepted")


def test_step5a_rejects_noncurrent_line_status():
    try:
        adapter.validate_fresh_payload(
            _payload(line_status="suspended"),
            requested_sportsbook="FanDuel",
            now_utc=NOW,
        )
    except ValueError as exc:
        assert str(exc) == "unsafe_noncurrent_line_status:suspended"
    else:
        raise AssertionError("suspended line was accepted")


def test_step5a_loader_fails_stale_market_to_empty_zero_weight_payload(monkeypatch):
    monkeypatch.setattr(
        adapter.frozen,
        "load_odds_for_date",
        lambda target_date, sportsbook: (
            _payload(captured_at="2026-09-10T04:10:00+00:00"),
            {
                "status": "GREEN",
                "requested_date": "2026-09-10",
                "sportsbook": sportsbook,
                "game_count": 1,
                "identity_verified_rows": 1,
                "projection_weight": 0.0,
                "market_context_only": True,
                "may_modify_projection": False,
                "error": "",
            },
        ),
    )
    monkeypatch.setattr(adapter, "_utc_now", lambda: NOW)

    adapter.load_odds_for_date.clear()
    payload, diag = adapter.load_odds_for_date("2026-09-10", "FanDuel")
    adapter.load_odds_for_date.clear()

    assert payload["games"] == []
    assert payload["game_count"] == 0
    assert payload["market_semantics"]["projection_weight"] == 0.0
    assert diag["status"] == "STALE"
    assert diag["freshness_status"] == "STALE"
    assert diag["projection_weight"] == 0.0
    assert diag["may_modify_projection"] is False


def test_step5a_reuses_frozen_event_id_attachment_path():
    assert adapter.FROZEN_ADAPTER == "cfb_over_under_market_adapter_v1"
    assert adapter.attach_market_lines is adapter.frozen.attach_market_lines
    assert adapter.market_line is adapter.frozen.market_line
