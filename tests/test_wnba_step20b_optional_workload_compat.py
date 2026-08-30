from __future__ import annotations

from datetime import date

import pytest

from sports_api import wnba_schedule_context as schedule_context
from sports_api import wnba_step20b_optional_workload_compat as compat
from sports_api import wnba_step7g_first_party_history as first_party


def _raise_not_found_chain():
    try:
        raise first_party.WNBAStep7GFirstPartyNotFoundError(
            "Official WNBA.com page missing for historical game 1022600036"
        )
    except first_party.WNBAStep7GFirstPartyNotFoundError as exc:
        raise schedule_context.WNBARestTravelUpstreamError(
            "Official WNBA.com box score could not supply Step 4J game 1022600036."
        ) from exc


def test_missing_historical_first_party_box_is_explicitly_fail_soft(monkeypatch):
    monkeypatch.setattr(compat, "_ORIGINAL_OBSERVED_WORKLOAD", lambda *args, **kwargs: _raise_not_found_chain())

    result = compat.get_observed_workload_step20b(
        "las-vegas-aces",
        2026,
        date(2026, 8, 30),
    )

    assert result["available"] is False
    assert result["included"] is True
    assert result["classification"] == "optional_observed_workload_unavailable"
    assert result["reason"] == "historical_official_box_score_not_found"
    assert result["historical_game_id"] == "1022600036"
    assert result["team_minutes_previous_7_days"] is None
    assert result["completed_games_previous_7_days"] is None
    assert result["verification"]["required_schedule_rest_travel_preserved"] is True
    assert result["verification"]["values_fabricated"] is False


def test_non_not_found_observed_workload_failure_stays_fail_closed(monkeypatch):
    def upstream(*args, **kwargs):
        raise schedule_context.WNBARestTravelUpstreamError("required upstream transport failed")

    monkeypatch.setattr(compat, "_ORIGINAL_OBSERVED_WORKLOAD", upstream)

    with pytest.raises(schedule_context.WNBARestTravelUpstreamError, match="required upstream transport failed"):
        compat.get_observed_workload_step20b("seattle-storm", 2026, date(2026, 8, 30))


def test_successful_observed_workload_is_returned_unchanged(monkeypatch):
    expected = {
        "source": "official",
        "completed_games_previous_7_days": 3,
        "team_minutes_previous_7_days": 605.0,
        "nested": {"value": 1},
    }
    monkeypatch.setattr(compat, "_ORIGINAL_OBSERVED_WORKLOAD", lambda *args, **kwargs: expected)

    result = compat.get_observed_workload_step20b("new-york-liberty", 2026, date(2026, 8, 30))

    assert result is expected


def test_installer_wraps_only_step4n_observed_workload_and_reports_guardrails(monkeypatch):
    monkeypatch.setattr(schedule_context, "_observed_workload", compat._ORIGINAL_OBSERVED_WORKLOAD)
    monkeypatch.setattr(compat, "_INSTALLED", False)

    status = compat.install_step20b_optional_workload_compat()

    assert schedule_context._observed_workload is compat.get_observed_workload_step20b
    assert status["installed"] is True
    assert status["binding_active"] is True
    guards = status["guardrails"]
    assert guards["first_party_not_found_only"] is True
    assert guards["other_observed_workload_exceptions_reraised"] is True
    assert guards["required_schedule_rest_travel_failures_relaxed"] is False
    assert guards["unavailable_metrics_are_none_not_zero"] is True
    assert guards["workload_values_fabricated"] is False
    assert guards["projection_math_modified"] is False
    assert guards["readiness_relaxed"] is False
    assert guards["monte_carlo_simulation_count_modified"] is False
    assert guards["monte_carlo_batch_size_modified"] is False
