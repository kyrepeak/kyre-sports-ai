from copy import deepcopy
from pathlib import Path
import sys

import pytest
import requests

import wnba_api_client_v1 as api
import wnba_streamlit_consumer_v2 as v2


def _semantics():
    return {
        "read_only_get": True, "in_memory_snapshot_only": True,
        "database_connection_opened": False, "database_read_performed": False,
        "database_write_performed": False, "scheduler_started": False,
        "scheduler_cycle_triggered": False, "sportsbook_network_called": False,
        "projection_run": False, "monte_carlo_run": False,
        "wager_action_performed": False, "database_secret_exposed": False,
        "new_render_service_created": False,
    }


def _card():
    return {
        "display_rank": 1, "frozen_rank": 1, "ranking": "pure_probability",
        "candidate_id": "c1", "qualification": "qualified",
        "player": {"player_id": 1, "player_name": "Example Player", "team_key": "ATL", "opponent_team_key": "NY", "game_id": "g1"},
        "prop": {"stat": "points", "stat_label": "Points", "side": "over", "line": 15.5, "pick": "OVER 15.5"},
        "market": {"sportsbook": "DraftKings", "american_odds": -110, "decimal_odds": 1.91, "captured_at_utc": "2026-08-29T01:30:00+00:00", "age_seconds_at_evaluation": 5.0},
        "model": {"resolved_fair_probability": .63, "resolved_fair_percentage": 63.0, "raw_win_probability": .62, "raw_win_percentage": 62.0, "push_probability": .01, "push_percentage": 1.0, "fair_price": {"available": True, "probability": .63, "percentage": 63.0, "decimal_odds": 1.5873, "american_odds": -170}, "simulations": 5_000_000, "batch_size": 100_000, "converged": True},
        "consensus": {"no_vig_probability": .51, "no_vig_percentage": 51.0, "edge_probability": .12, "edge_percentage_points": 12.0, "book_count_at_exact_line": 2, "market_probability_range_percentage_points": 1.0},
        "value": {"ev_per_unit": .2, "ev_roi_percentage": 20.0},
        "qualification_margin": {}, "lineage": {},
    }


def _payload(*, available=True, age=10.0, stale=False, reason=None):
    return {
        "data_type": "wnba_step18a_streamlit_consumer_latest",
        "schema_version": "wnba_step_18a_streamlit_consumer_v1",
        "consumer_version": "test", "source": "test",
        "generated_at_utc": "2026-08-29T01:30:10+00:00",
        "enabled": True, "available": available,
        "reason": reason or ("board_ready" if available else "not_executed"),
        "slate_date": "2026-08-28", "health": "healthy",
        "snapshot": {"captured_at_utc": "2026-08-29T01:30:00+00:00", "source_generated_at_utc": "2026-08-29T01:29:59+00:00", "age_seconds": age, "stale_after_seconds": 180, "stale": stale, "snapshot_content_sha256": "a" * 64},
        "board": {"available": available, "ranking_method": "frozen_probability" if available else None, "requested_top_card_count": 5, "qualified_prop_count": 1 if available else 0, "top_card_count": 1 if available else 0, "full_requested_board_available": False, "top_n_forced": False, "primary_top_cards": [_card()] if available else [], "value_ranking": [], "reason": None if available else (reason or "not_executed")},
        "runtime": {"next_refresh_due_at_utc": "2026-08-29T01:31:00+00:00"},
        "lineage": {"step17d_frozen_runtime_sha": v2.EXPECTED_STEP17D_SHA, "source_step13c_reliability_content_sha256": "b" * 64, "source_step13a_scheduler_content_sha256": "c" * 64},
        "semantics": _semantics(),
    }


def test_frontend_age_defense_hides_card_even_if_api_stale_flag_lags():
    view = v2.normalize_consumer_payload(_payload(age=190.0, stale=False))
    assert view["state"] == "stale"
    assert view["available"] is False
    assert view["cards"] == []
    assert view["snapshot"]["effective_stale"] is True


def test_lineage_drift_fails_closed():
    payload = _payload()
    payload["lineage"]["step17d_frozen_runtime_sha"] = "0" * 40
    with pytest.raises(v2.WNBAStreamlitConsumerReliabilityError):
        v2.normalize_consumer_payload(payload)


def test_available_board_count_drift_fails_closed():
    payload = _payload()
    payload["board"]["top_card_count"] = 2
    with pytest.raises(v2.WNBAStreamlitConsumerReliabilityError):
        v2.normalize_consumer_payload(payload)


def test_current_no_board_stays_empty_and_current_when_top_n_metadata_is_omitted():
    payload = _payload(available=False, reason="not_executed")
    payload["board"].pop("top_n_forced")
    payload["board"].pop("top_card_count")
    view = v2.normalize_consumer_payload(payload)
    assert view["state"] == "unavailable"
    assert view["cards"] == []
    assert view["snapshot"]["effective_stale"] is False


def test_render_free_cold_start_retry_recovers_after_two_timeouts(monkeypatch):
    calls = []
    sleeps = []

    class Response:
        status_code = 200
        def json(self):
            return _payload(available=False)

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) < 3:
            raise requests.Timeout("cold start")
        return Response()

    monkeypatch.setattr(api.requests, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", lambda seconds: sleeps.append(seconds))
    client = api.KyreWNBAAPIClient(timeout_seconds=1, attempts=3)
    result = client.consumer_latest()
    assert result["reason"] == "not_executed"
    assert len(calls) == 3
    assert sleeps == [1.5, 3.0]


def test_step18c_bridge_import_failure_never_restores_legacy_compute(monkeypatch):
    import wnba_step18c_consumer_bridge_v1 as bridge
    real_import = bridge.importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == "wnba_daily_picks_hub_v36":
            raise ImportError("simulated V36 failure")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(bridge.importlib, "import_module", fake_import)
    result = bridge.install_step18c_consumer_bridge()
    assert result["installed"] is True
    assert result["fail_closed"] is True
    assert result["legacy_daily_picks_compute_fallback"] is False
    target = sys.modules["wnba_daily_picks_hub_v34"]
    assert target is sys.modules["wnba_daily_picks_hub_v4"]
    assert callable(target.render_wnba_daily_picks_hub)


def test_v36_maps_not_executed_to_friendly_status(monkeypatch):
    import wnba_daily_picks_hub_v36 as v36
    seen = []

    class FakeST:
        def info(self, message): seen.append(("info", message))
        def caption(self, message): seen.append(("caption", message))

    monkeypatch.setattr(v36, "st", FakeST())
    v36._render_status_reliable(v2.normalize_consumer_payload(_payload(available=False, reason="not_executed")))
    assert any(kind == "info" and "latest scheduler cycle" in message for kind, message in seen)


def test_root_app_installs_step18c_before_frozen_source_and_no_longer_calls_step18b():
    text = Path("app.py").read_text()
    assert "install_step18c_consumer_bridge" in text
    assert "_STEP18C_WNBA_CONSUMER_BRIDGE" in text
    assert text.index("_STEP18C_WNBA_CONSUMER_BRIDGE") < text.index("source = _load_frozen_pre_live_app()")
    assert "_STEP18B_WNBA_CONSUMER_BRIDGE =" not in text


def test_step18c_new_layers_never_import_backend_runtime():
    for path in ("wnba_streamlit_consumer_v2.py", "wnba_daily_picks_hub_v36.py", "wnba_step18c_consumer_bridge_v1.py"):
        text = Path(path).read_text()
        assert "from sports_api" not in text
        assert "import sports_api" not in text
