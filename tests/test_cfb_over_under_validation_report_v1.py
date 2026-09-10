from __future__ import annotations

import pytest

from cfb_over_under_shadow_history_v1 import append_history_file
from cfb_over_under_validation_report_v1 import (
    ValidationReportError,
    build_history_validation_report,
)


def _row(game_id="401858213", *, probability=0.62, outcome=1):
    return {
        "game_id": game_id,
        "identity_verified": True,
        "source_mode": "live_shadow",
        "market_type": "over",
        "conference": "ACC",
        "model_probability": probability,
        "outcome": outcome,
        "model_edge_at_signal": 2.5,
        "model_edge_at_close": 1.5,
        "market_total_at_signal": 62.5,
        "market_total_at_close": 63.5,
        "projection_weight": 0.0,
        "may_modify_projection": False,
    }


def test_report_loads_history_and_builds_validation(tmp_path):
    path = tmp_path / "history.jsonl"
    append_history_file(path, [_row()], captured_at_utc="2026-09-10T17:00:00+00:00")

    result = build_history_validation_report(path)

    assert result["record_count"] == 1
    assert result["validation"]["overall"]["sample_size"] == 1
    assert result["validation"]["overall"]["mean_clv_points"] == 1.0
    assert result["diagnostics"]["read_only"] is True
    assert result["diagnostics"]["projection_weight"] == 0.0
    assert result["diagnostics"]["core_model_frozen"] is True


def test_report_flattens_multiple_batches(tmp_path):
    path = tmp_path / "history.jsonl"
    append_history_file(path, [_row()], captured_at_utc="2026-09-10T17:00:00+00:00")
    append_history_file(path, [_row("401858214", probability=0.40, outcome=0)], captured_at_utc="2026-09-10T17:05:00+00:00")

    result = build_history_validation_report(path)

    assert result["record_count"] == 2
    assert result["validation"]["overall"]["sample_size"] == 2
    assert result["validation"]["by_conference"]["ACC"]["sample_size"] == 2


def test_empty_history_fails_closed(tmp_path):
    path = tmp_path / "missing.jsonl"
    with pytest.raises(ValidationReportError, match="unsafe_empty_shadow_history"):
        build_history_validation_report(path)
