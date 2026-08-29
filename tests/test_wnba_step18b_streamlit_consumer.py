from copy import deepcopy
from pathlib import Path
import sys

import pytest

import wnba_api_client_v1 as api
import wnba_streamlit_consumer_v1 as consumer


def _card():
    return {
        "display_rank": 1,
        "frozen_rank": 1,
        "ranking": "pure_probability",
        "candidate_id": "c1",
        "qualification": "qualified",
        "player": {
            "player_id": 123,
            "player_name": "Example Player",
            "team_key": "ATL",
            "opponent_team_key": "NY",
            "game_id": "g1",
        },
        "prop": {
            "stat": "points",
            "stat_label": "Points",
            "side": "over",
            "line": 15.5,
            "pick": "OVER 15.5",
        },
        "market": {
            "sportsbook": "DraftKings",
            "american_odds": -110,
            "decimal_odds": 1.90909091,
            "captured_at_utc": "2026-08-29T01:20:00+00:00",
            "age_seconds_at_evaluation": 8.2,
        },
        "model": {
            "resolved_fair_probability": 0.63,
            "resolved_fair_percentage": 63.0,
            "raw_win_probability": 0.62,
            "raw_win_percentage": 62.0,
            "push_probability": 0.01,
            "push_percentage": 1.0,
            "fair_price": {
                "available": True,
                "probability": 0.63,
                "percentage": 63.0,
                "decimal_odds": 1.58730159,
                "american_odds": -170,
            },
            "simulations": 5_000_000,
            "batch_size": 100_000,
            "converged": True,
        },
        "consensus": {
            "no_vig_probability": 0.51,
            "no_vig_percentage": 51.0,
            "edge_probability": 0.12,
            "edge_percentage_points": 12.0,
            "book_count_at_exact_line": 2,
            "market_probability_range_percentage_points": 1.2,
        },
        "value": {"ev_per_unit": 0.2027, "ev_roi_percentage": 20.27},
        "qualification_margin": {},
        "lineage": {},
    }


def _semantics():
    return {
        "read_only_get": True,
        "in_memory_snapshot_only": True,
        "database_connection_opened": False,
        "database_read_performed": False,
        "database_write_performed": False,
        "scheduler_started": False,
        "scheduler_cycle_triggered": False,
        "sportsbook_network_called": False,
        "projection_run": False,
        "monte_carlo_run": False,
        "wager_action_performed": False,
        "database_secret_exposed": False,
        "new_render_service_created": False,
    }


def _payload(*, available=True, stale=False, enabled=True, reason=None):
    cards = [_card()] if available else []
    return {
        "data_type": consumer.EXPECTED_DATA_TYPE,
        "schema_version": consumer.EXPECTED_SCHEMA_VERSION,
        "consumer_version": "test",
        "source": "test",
        "generated_at_utc": "2026-08-29T01:20:10+00:00",
        "enabled": enabled,
        "available": available and enabled,
        "reason": reason or ("board_ready" if available else "not_executed"),
        "slate_date": "2026-08-28" if enabled else None,
        "health": "healthy" if enabled else None,
        "snapshot": {
            "captured_at_utc": "2026-08-29T01:20:00+00:00" if enabled else None,
            "source_generated_at_utc": "2026-08-29T01:19:59+00:00" if enabled else None,
            "age_seconds": 10.0 if enabled else None,
            "stale_after_seconds": 180,
            "stale": stale if enabled else False,
            "snapshot_content_sha256": "a" * 64 if enabled else None,
        },
        "board": {
            "available": available and enabled,
            "ranking_method": "frozen_probability" if available else None,
            "requested_top_card_count": 5 if enabled else None,
            "qualified_prop_count": 1 if available else 0,
            "top_card_count": 1 if available else 0,
            "full_requested_board_available": False,
            "top_n_forced": False,
            "primary_top_cards": cards if enabled else [],
            "value_ranking": [],
            "reason": None if available else (reason or "not_executed"),
        },
        "runtime": {"next_refresh_due_at_utc": "2026-08-29T01:21:00+00:00"} if enabled else {},
        "lineage": {},
        "semantics": _semantics(),
    }


def test_ready_board_is_normalized_without_changing_rank_or_model_values():
    view = consumer.normalize_consumer_payload(_payload())
    assert view["state"] == "ready"
    assert view["available"] is True
    assert len(view["cards"]) == 1
    assert view["cards"][0]["display_rank"] == 1
    assert view["cards"][0]["model"]["resolved_fair_probability"] == 0.63
    assert view["cards"][0]["market"]["american_odds"] == -110


def test_stale_snapshot_hides_all_cards_fail_closed():
    view = consumer.normalize_consumer_payload(_payload(stale=True))
    assert view["state"] == "stale"
    assert view["available"] is False
    assert view["cards"] == []


def test_current_unavailable_board_never_recycles_old_cards():
    view = consumer.normalize_consumer_payload(_payload(available=False, reason="not_executed"))
    assert view["state"] == "unavailable"
    assert view["reason"] == "not_executed"
    assert view["cards"] == []


def test_unsafe_consumer_semantic_drift_is_rejected():
    payload = _payload()
    payload["semantics"]["sportsbook_network_called"] = True
    with pytest.raises(consumer.WNBAStreamlitConsumerError):
        consumer.normalize_consumer_payload(payload)


def test_non_converged_or_non_5m_card_is_rejected():
    payload = _payload()
    payload["board"]["primary_top_cards"][0]["model"]["simulations"] = 1_000
    with pytest.raises(consumer.WNBAStreamlitConsumerError):
        consumer.normalize_consumer_payload(payload)


def test_client_consumer_latest_uses_only_certified_get_path(monkeypatch):
    client = api.KyreWNBAAPIClient()
    seen = []

    def fake_get(path, *, params=None):
        seen.append((path, params))
        return _payload()

    monkeypatch.setattr(client, "get_json", fake_get)
    result = client.consumer_latest()
    assert result["data_type"] == consumer.EXPECTED_DATA_TYPE
    assert seen == [("/api/v1/wnba/consumer/latest", None)]


def test_load_error_returns_explicit_empty_error_state():
    class BrokenClient:
        def consumer_latest(self):
            raise api.KyreWNBAAPIError("wake timeout")

    view = consumer.load_latest_daily_picks(BrokenClient())
    assert view["state"] == "error"
    assert view["cards"] == []
    assert view["reason"] == "consumer_read_failed"
    assert view["error_type"] == "KyreWNBAAPIError"


def test_step18b_bridge_routes_historical_daily_picks_names_to_v35():
    import wnba_step18b_consumer_bridge_v1 as bridge

    result = bridge.install_step18b_consumer_bridge()
    assert result["installed"] is True
    assert result["legacy_daily_picks_compute_fallback"] is False
    assert sys.modules["wnba_daily_picks_hub_v34"] is sys.modules["wnba_daily_picks_hub_v35"]
    assert sys.modules["wnba_daily_picks_hub_v4"] is sys.modules["wnba_daily_picks_hub_v35"]


def test_v35_card_html_uses_certified_card_fields_and_escapes_player_name():
    import wnba_daily_picks_hub_v35 as v35

    card = _card()
    card["player"]["player_name"] = "A <B>"
    html = v35._card_html(card)
    assert "A &lt;B&gt;" in html
    assert "OVER 15.5" in html
    assert "DraftKings" in html
    assert "63.0%" in html
    assert "5,000,000" in html


def test_root_app_keeps_frozen_replay_and_installs_step18b_before_source_exec():
    text = Path("app.py").read_text()
    assert 'FROZEN_PRE_LIVE_COMMIT = "235d7ddc47de93657910a1f0cf9928f2a9f0f758"' in text
    assert "install_step18b_consumer_bridge" in text
    assert text.index("_STEP18B_WNBA_CONSUMER_BRIDGE") < text.index("source = _load_frozen_pre_live_app()")


def test_step18b_files_do_not_import_sports_api_backend_runtime():
    for path in (
        "wnba_streamlit_consumer_v1.py",
        "wnba_daily_picks_hub_v35.py",
        "wnba_step18b_consumer_bridge_v1.py",
    ):
        text = Path(path).read_text()
        assert "from sports_api" not in text
        assert "import sports_api" not in text


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
