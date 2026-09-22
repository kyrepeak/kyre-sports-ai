from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import ModuleType
import sys

import pandas as pd
import pytest

import mlb_step9e_live_market_consumer_v1 as step9e


GAME_ID = 824472
NOW = datetime(2026, 9, 1, 16, 10, 0, tzinfo=timezone.utc)


def _game(game_id=GAME_ID):
    return {
        "official_game_id": game_id,
        "sportsbook_event_id": "36014929",
        "sportsbook_event_name": "Away @ Home",
        "scheduled_start_utc": "2026-09-01T15:00:00+00:00",
        "sportsbook": "FanDuel",
        "market_phase": "IN_PLAY",
        "in_play": True,
        "fully_priced": True,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "away_team": {"id": 135, "name": "Away Club"},
        "home_team": {"id": 113, "name": "Home Club"},
        "markets": {
            "moneyline": {"away_odds": 125, "home_odds": -145},
            "run_line": {
                "away_line": 1.5,
                "away_odds": -105,
                "home_line": -1.5,
                "home_odds": -115,
            },
            "total": {"line": 7.5, "over_odds": -110, "under_odds": -110},
        },
    }


def _payload(game_id=GAME_ID, *, collected_at=NOW, games=None):
    return {
        "data_type": "mlb_inplay_odds_api_response_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "transport": "anonymous_public_get_only",
        "http_methods": ["GET"],
        "market_phase": "IN_PLAY",
        "collected_at_utc": collected_at.isoformat(),
        "requested_official_game_id": game_id,
        "fully_priced_only": True,
        "game_count": 1,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "games": deepcopy(games) if games is not None else [_game(game_id)],
    }


def test_snapshot_maps_exact_id_fanduel_payload_to_existing_v192_shape():
    payload = _payload()
    payload_copy = deepcopy(payload)
    snap = step9e._snapshot_from_payload(
        payload,
        official_game_id=GAME_ID,
        as_of_utc=NOW + timedelta(seconds=12),
    )

    assert snap is not None
    assert snap["official_game_id"] == GAME_ID
    assert snap["source"] == "FanDuel"
    assert snap["match_method"] == "official_mlb_game_id_exact"
    assert snap["fallback_matching_used"] is False
    assert snap["fuzzy_matching_used"] is False
    assert snap["synthetic_game_id_used"] is False
    assert snap["home_spread"] == -1.5
    assert snap["total_line"] == 7.5
    assert snap["away"] == "Away Club"
    assert snap["home"] == "Home Club"
    assert snap["event_id"] == "36014929"
    assert len(snap["rows"]) == 1
    row = snap["rows"][0]
    assert row == {
        "Book": "FanDuel",
        "Away ML": 125,
        "Home ML": -145,
        "Away RL": "+1.5 (-105)",
        "Home RL": "-1.5 (-115)",
        "Over": "O 7.5 (-110)",
        "Under": "U 7.5 (-110)",
        "updatedAt": NOW.isoformat(),
        "home_hdp": -1.5,
        "total_line": 7.5,
        "age_seconds": 12,
    }
    assert payload == payload_copy


def test_snapshot_identity_is_gamepk_only_not_team_names():
    payload = _payload()
    payload["games"][0]["away_team"]["name"] = "Completely Wrong Away Name"
    payload["games"][0]["home_team"]["name"] = "Completely Wrong Home Name"
    snap = step9e._snapshot_from_payload(
        payload,
        official_game_id=GAME_ID,
        as_of_utc=NOW,
    )
    assert snap is not None
    assert snap["official_game_id"] == GAME_ID


def test_snapshot_rejects_wrong_requested_or_row_game_id():
    wrong_request = _payload()
    wrong_request["requested_official_game_id"] = GAME_ID + 1
    assert step9e._snapshot_from_payload(
        wrong_request,
        official_game_id=GAME_ID,
        as_of_utc=NOW,
    ) is None

    wrong_row = _payload()
    wrong_row["games"][0]["official_game_id"] = GAME_ID + 1
    assert step9e._snapshot_from_payload(
        wrong_row,
        official_game_id=GAME_ID,
        as_of_utc=NOW,
    ) is None


def test_snapshot_rejects_stale_or_unproven_freshness():
    stale = _payload(collected_at=NOW - timedelta(seconds=181))
    assert step9e._snapshot_from_payload(
        stale,
        official_game_id=GAME_ID,
        as_of_utc=NOW,
    ) is None

    missing = _payload()
    missing["collected_at_utc"] = None
    assert step9e._snapshot_from_payload(
        missing,
        official_game_id=GAME_ID,
        as_of_utc=NOW,
    ) is None


def test_snapshot_rejects_non_inplay_incomplete_or_tampered_contract():
    variants = []
    pregame = _payload(); pregame["games"][0]["in_play"] = False; variants.append(pregame)
    not_full = _payload(); not_full["games"][0]["fully_priced"] = False; variants.append(not_full)
    fuzzy = _payload(); fuzzy["fuzzy_matching_used"] = True; variants.append(fuzzy)
    synthetic = _payload(); synthetic["games"][0]["synthetic_game_id_used"] = True; variants.append(synthetic)
    wrong_source = _payload(); wrong_source["source"] = "OtherBook"; variants.append(wrong_source)
    missing_market = _payload(); missing_market["games"][0]["markets"].pop("total"); variants.append(missing_market)
    bad_price = _payload(); bad_price["games"][0]["markets"]["moneyline"]["home_odds"] = None; variants.append(bad_price)

    for payload in variants:
        assert step9e._snapshot_from_payload(
            payload,
            official_game_id=GAME_ID,
            as_of_utc=NOW,
        ) is None


def test_snapshot_identity_types_are_strict_but_ascii_serialized_integer_is_allowed():
    assert step9e.snapshot_for_official_game_id(True, payload_getter=lambda game_id: _payload()) is None
    assert step9e.snapshot_for_official_game_id(824472.0, payload_getter=lambda game_id: _payload()) is None
    assert step9e.snapshot_for_official_game_id("８２４４７２", payload_getter=lambda game_id: _payload()) is None

    seen = []
    snap = step9e.snapshot_for_official_game_id(
        str(GAME_ID),
        payload_getter=lambda game_id: seen.append(game_id) or _payload(),
        as_of_utc=NOW,
    )
    assert snap is not None
    assert seen == [GAME_ID]


def _fake_market_modules(monkeypatch, *, legacy_key="legacy-key"):
    v192 = ModuleType("live_game_hub_v192")
    v1921 = ModuleType("live_game_hub_v1921")
    calls = {"setup": [], "snapshots": [], "books": 0}

    def legacy_setup(prefix="live_odds"):
        calls["setup"].append(prefix)
        return legacy_key

    def legacy_books():
        calls["books"] += 1
        return "FanDuel,DraftKings"

    def legacy_snapshots(games_df, api_key=None, bookmakers=None):
        calls["snapshots"].append(
            {
                "api_key": api_key,
                "bookmakers": bookmakers,
                "records": games_df.to_dict("records") if games_df is not None else None,
            }
        )
        return {GAME_ID: {"legacy": True}}

    sentinel_market_sync = lambda s, game: (s, game)
    for module in (v192, v1921):
        module.render_connection_setup = legacy_setup
        module.get_bookmakers = legacy_books
        module.snapshots_for_games = legacy_snapshots
        module._market_sync = sentinel_market_sync

    monkeypatch.setitem(sys.modules, "live_game_hub_v192", v192)
    monkeypatch.setitem(sys.modules, "live_game_hub_v1921", v1921)
    return v192, v1921, calls, sentinel_market_sync


def _v19_df(game_pk=GAME_ID):
    return pd.DataFrame(
        [
            {
                "game_pk": game_pk,
                "away_team": "Legacy Away Name",
                "home_team": "Legacy Home Name",
            }
        ]
    )


def test_installer_patches_transport_only_and_api_success_skips_legacy(monkeypatch):
    v192, v1921, calls, original_market_sync = _fake_market_modules(monkeypatch)
    api_snap = step9e._snapshot_from_payload(
        _payload(), official_game_id=GAME_ID, as_of_utc=NOW
    )
    monkeypatch.setattr(step9e, "snapshot_for_official_game_id", lambda game_id: deepcopy(api_snap))

    result = step9e.install_step9e_live_market_consumer()
    frame = _v19_df()
    frame_copy = frame.copy(deep=True)
    assert v1921.render_connection_setup("v192_test") == step9e.API_SENTINEL
    snaps = v1921.snapshots_for_games(frame, step9e.API_SENTINEL, "Anything")

    assert snaps[GAME_ID]["official_game_id"] == GAME_ID
    assert calls["setup"] == []
    assert calls["snapshots"] == []
    assert v1921.get_bookmakers() == "FanDuel"
    assert v192._market_sync is original_market_sync
    assert v1921._market_sync is original_market_sync
    pd.testing.assert_frame_equal(frame, frame_copy)
    assert result["v1922_market_sync_function_preserved"] is True
    assert result["legacy_odds_api_io_fallback_preserved"] is True
    for flag in step9e.PROTECTED_FALSE_FLAGS:
        assert result[flag] is False
        assert step9e.consumer_status()[flag] is False
    status = step9e.consumer_status()
    assert status["api_attempted"] is True
    assert status["api_used"] is True
    assert status["legacy_fallback_used"] is False


def test_api_network_failure_delegates_to_original_odds_api_path(monkeypatch):
    v192, v1921, calls, _ = _fake_market_modules(monkeypatch, legacy_key="real-legacy-key")

    def fail(game_id):
        raise TimeoutError("hosted API offline")

    monkeypatch.setattr(step9e, "snapshot_for_official_game_id", fail)
    step9e.install_step9e_live_market_consumer()
    result = v1921.snapshots_for_games(_v19_df(), step9e.API_SENTINEL, "ignored")

    assert result == {GAME_ID: {"legacy": True}}
    assert calls["setup"] == ["v192_step9e_fallback"]
    assert len(calls["snapshots"]) == 1
    assert calls["snapshots"][0]["api_key"] == "real-legacy-key"
    assert calls["snapshots"][0]["bookmakers"] == "FanDuel,DraftKings"
    status = step9e.consumer_status()
    assert status["api_used"] is False
    assert status["legacy_fallback_used"] is True
    assert status["failure"] == "TimeoutError"


def test_contract_rejection_uses_legacy_fallback(monkeypatch):
    v192, v1921, calls, _ = _fake_market_modules(monkeypatch, legacy_key="legacy-key")
    monkeypatch.setattr(step9e, "snapshot_for_official_game_id", lambda game_id: None)
    step9e.install_step9e_live_market_consumer()
    result = v1921.snapshots_for_games(_v19_df(), step9e.API_SENTINEL, "ignored")
    assert result == {GAME_ID: {"legacy": True}}
    assert calls["setup"] == ["v192_step9e_fallback"]
    assert step9e.consumer_status()["legacy_fallback_used"] is True
    assert step9e.consumer_status()["failure"] == "RuntimeError"


def test_no_legacy_key_fails_open_to_no_market_snapshot(monkeypatch):
    v192, v1921, calls, _ = _fake_market_modules(monkeypatch, legacy_key=None)
    monkeypatch.setattr(step9e, "snapshot_for_official_game_id", lambda game_id: None)
    step9e.install_step9e_live_market_consumer()
    assert v1921.snapshots_for_games(_v19_df(), step9e.API_SENTINEL, "ignored") == {}
    assert calls["setup"] == ["v192_step9e_fallback"]
    assert calls["snapshots"] == []


def test_invalid_v19_game_identity_never_calls_hosted_api(monkeypatch):
    v192, v1921, calls, _ = _fake_market_modules(monkeypatch)
    api_calls = []
    monkeypatch.setattr(
        step9e,
        "snapshot_for_official_game_id",
        lambda game_id: api_calls.append(game_id) or None,
    )
    step9e.install_step9e_live_market_consumer()

    for invalid in (True, 824472.0, "８２４４７２"):
        v1921.snapshots_for_games(_v19_df(invalid), step9e.API_SENTINEL, "ignored")
    assert api_calls == []


def test_serialized_ascii_v19_game_identity_uses_api(monkeypatch):
    v192, v1921, calls, _ = _fake_market_modules(monkeypatch)
    seen = []
    api_snap = step9e._snapshot_from_payload(
        _payload(), official_game_id=GAME_ID, as_of_utc=NOW
    )
    monkeypatch.setattr(
        step9e,
        "snapshot_for_official_game_id",
        lambda game_id: seen.append(game_id) or deepcopy(api_snap),
    )
    step9e.install_step9e_live_market_consumer()
    result = v1921.snapshots_for_games(_v19_df(str(GAME_ID)), step9e.API_SENTINEL, "ignored")
    assert seen == [GAME_ID]
    assert result[GAME_ID]["official_game_id"] == GAME_ID
    assert calls["snapshots"] == []


def test_double_install_is_idempotent_and_does_not_stack_fallback(monkeypatch):
    v192, v1921, calls, original_market_sync = _fake_market_modules(monkeypatch)
    monkeypatch.setattr(step9e, "snapshot_for_official_game_id", lambda game_id: None)
    step9e.install_step9e_live_market_consumer()
    step9e.install_step9e_live_market_consumer()
    result = v1921.snapshots_for_games(_v19_df(), step9e.API_SENTINEL, "ignored")
    assert result == {GAME_ID: {"legacy": True}}
    assert len(calls["setup"]) == 1
    assert len(calls["snapshots"]) == 1
    assert v1921._market_sync is original_market_sync


def test_installer_does_not_patch_any_v19_model_functions(monkeypatch):
    v192, v1921, calls, _ = _fake_market_modules(monkeypatch)
    model_panel = object()
    edge_dashboard = object()
    v192._ORIGINAL_LIVE_MODEL_PANEL = model_panel
    v192._render_edge_dashboard = edge_dashboard
    step9e.install_step9e_live_market_consumer()
    assert v192._ORIGINAL_LIVE_MODEL_PANEL is model_panel
    assert v192._render_edge_dashboard is edge_dashboard
