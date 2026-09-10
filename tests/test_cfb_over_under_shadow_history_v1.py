from __future__ import annotations

import json

import pytest

import cfb_over_under_shadow_history_v1 as history


def _row(**overrides):
    row = {
        "game_id": "401858213",
        "identity_verified": True,
        "source_mode": "live_shadow",
        "projection_weight": 0.0,
        "may_modify_projection": False,
        "market_type": "game_total",
        "model_probability": 0.61,
        "outcome": 1,
        "model_edge_at_signal": 2.5,
        "model_edge_at_close": 1.5,
        "market_total_at_signal": 62.5,
        "market_total_at_close": 63.5,
        "conference": "ACC",
    }
    row.update(overrides)
    return row


def test_build_snapshot_preserves_safety_contract():
    result = history.build_history_snapshot([_row()], captured_at_utc="2026-09-10T17:00:00+00:00")
    assert result["record_count"] == 1
    assert result["records"][0]["game_id"] == "401858213"
    assert result["diagnostics"]["live_shadow_only"] is True
    assert result["diagnostics"]["official_event_id_only"] is True
    assert result["diagnostics"]["projection_weight"] == 0.0
    assert result["diagnostics"]["may_modify_projection"] is False


def test_non_shadow_row_fails_closed():
    with pytest.raises(history.ShadowHistoryError, match="unsafe_non_shadow_row"):
        history.build_history_snapshot([_row(source_mode="production")])


def test_synthetic_event_id_fails_closed():
    with pytest.raises(history.ShadowHistoryError, match="unsafe_non_official_event_id"):
        history.build_history_snapshot([_row(game_id="synthetic-401858213")])


def test_nonzero_projection_weight_fails_closed():
    with pytest.raises(history.ShadowHistoryError, match="unsafe_nonzero_projection_weight"):
        history.build_history_snapshot([_row(projection_weight=0.01)])


def test_append_and_load_jsonl_round_trip(tmp_path):
    target = tmp_path / "history.jsonl"
    history.append_history_file(target, [_row()], captured_at_utc="2026-09-10T17:00:00+00:00")
    history.append_history_file(target, [_row(game_id="401858214")], captured_at_utc="2026-09-10T18:00:00+00:00")
    rows = history.load_history_records(target)
    assert [row["game_id"] for row in rows] == ["401858213", "401858214"]
    assert len(target.read_text(encoding="utf-8").splitlines()) == 2


def test_invalid_jsonl_fails_closed(tmp_path):
    target = tmp_path / "history.jsonl"
    target.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(history.ShadowHistoryError, match="unsafe_invalid_jsonl:1"):
        history.load_history_records(target)
