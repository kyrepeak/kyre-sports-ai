from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step11a_provider_contract_v1 import validate_market_provider_game_snapshot
from sports_api.collectors.mlb_draftkings_provider import (
    ADAPTER_STATUS,
    DRAFTKINGS_EVENT_GAMEPK_MAP_ENV,
    DRAFTKINGS_TIMEOUT_ENV,
    DRAFTKINGS_URLS_ENV,
    FINAL_CERTIFICATION_MARKER,
    MLBDraftKingsProviderError,
    MLBDraftKingsProviderNotReadyError,
    MLBDraftKingsProviderUpstreamError,
    PROVIDER_KEY,
    PROVIDER_NAME,
    STEP11B_BASE_MAIN_SHA,
    adapter_manifest,
    collect_draftkings_provider_snapshots,
    describe_draftkings_provider,
    normalize_draftkings_game_document,
    resolve_draftkings_urls,
    resolve_event_gamepk_map,
)

EVENT = "dk-mlb-1001"
GAMEPK = 777001
OBSERVED = "2026-09-01T17:30:00Z"
URL = "https://sportsbook.draftkings.com/api/example/mlb"


def modern_document(*, in_play=False):
    return {
        "events": [{"id": EVENT}],
        "markets": [
            {"id": "m-money", "eventId": EVENT, "name": "Moneyline", "status": "OPEN", "inPlay": in_play, "marketTime": "2026-09-01T23:10:00Z"},
            {"id": "m-run", "eventId": EVENT, "name": "Run Line", "status": "OPEN", "inPlay": in_play, "marketTime": "2026-09-01T23:10:00Z"},
            {"id": "m-total", "eventId": EVENT, "name": "Total Runs", "status": "OPEN", "inPlay": in_play, "marketTime": "2026-09-01T23:10:00Z"},
        ],
        "selections": [
            {"id": "s-ma", "marketId": "m-money", "label": "Away", "oddsAmerican": "+115"},
            {"id": "s-mh", "marketId": "m-money", "label": "Home", "oddsAmerican": -125},
            {"id": "s-ra", "marketId": "m-run", "participantRole": "away", "points": "+1.5", "oddsAmerican": -105},
            {"id": "s-rh", "marketId": "m-run", "participantRole": "home", "points": -1.5, "oddsAmerican": "-115"},
            {"id": "s-to", "marketId": "m-total", "outcomeType": "over", "points": "8.5", "displayOdds": {"american": "+100"}},
            {"id": "s-tu", "marketId": "m-total", "outcomeType": "under", "points": 8.5, "americanOdds": -120},
        ],
    }


def legacy_document():
    return {
        "eventGroup": {
            "events": [{"id": EVENT}],
            "offers": [
                {"id": "lm", "eventId": EVENT, "label": "Money Line", "status": "OPEN", "inPlay": False, "outcomes": [
                    {"id": "lma", "side": "away", "oddsAmerican": 110},
                    {"id": "lmh", "side": "home", "oddsAmerican": -130},
                ]},
                {"id": "lr", "eventId": EVENT, "label": "Spread", "status": "OPEN", "inPlay": False, "outcomes": [
                    {"id": "lra", "side": "away", "line": 1.5, "oddsAmerican": -105},
                    {"id": "lrh", "side": "home", "line": -1.5, "oddsAmerican": -115},
                ]},
                {"id": "lt", "eventId": EVENT, "label": "Game Total", "status": "OPEN", "inPlay": False, "outcomes": [
                    {"id": "lto", "side": "over", "line": 9.0, "oddsAmerican": -110},
                    {"id": "ltu", "side": "under", "line": 9.0, "oddsAmerican": -110},
                ]},
            ],
        }
    }


def normalize(document=None, *, phase="PREGAME", gamepk=GAMEPK, mapping=None, event=EVENT, observed=OBSERVED, collected=None):
    return normalize_draftkings_game_document(
        modern_document() if document is None else document,
        provider_event_id=event,
        official_game_id=gamepk,
        event_gamepk_map={EVENT: GAMEPK} if mapping is None else mapping,
        market_phase=phase,
        observed_at_utc=observed,
        source_collected_at_utc=collected,
    )


def test_manifest_freezes_step11b_shadow_boundary():
    manifest = adapter_manifest()
    assert STEP11B_BASE_MAIN_SHA == "733206c8fe8c0d219c5d76b8706eca652507de30"
    assert manifest["adapter_status"] == ADAPTER_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert manifest["provider_key"] == PROVIDER_KEY == "draftkings"
    assert manifest["provider_name"] == PROVIDER_NAME == "DraftKings"
    for key in ("public_get_only", "explicit_endpoint_configuration_required", "exact_provider_event_to_gamepk_map_required", "shadow_adapter_only"):
        assert manifest[key] is True
    for key in ("default_unverified_endpoint_allowed", "team_name_join_allowed", "player_name_join_allowed", "fuzzy_matching_allowed", "synthetic_game_id_allowed", "price_fabrication_allowed", "fallback_price_fabrication_allowed", "login_or_account_session_allowed", "cookies_allowed", "browser_automation_allowed", "wager_actions_allowed", "production_api_wiring_added_by_step11b", "production_runtime_wiring_added_by_step11b", "persistence_schema_changed_by_step11b", "production_database_writes_enabled", "provider_consensus_enabled_by_step11b", "provider_failover_enabled_by_step11b"):
        assert manifest[key] is False
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


def test_modern_document_builds_fully_priced_step11a_snapshot():
    snapshot = normalize()
    assert snapshot["provider_key"] == "draftkings"
    assert snapshot["provider_name"] == "DraftKings"
    assert snapshot["official_game_id"] == GAMEPK
    assert snapshot["provider_event_id"] == EVENT
    assert snapshot["market_count"] == 3
    assert snapshot["fully_priced"] is True
    assert snapshot["markets"]["moneyline"]["away_odds"] == 115
    assert snapshot["markets"]["run_line"]["away_line"] == 1.5
    assert snapshot["markets"]["total"]["line"] == 8.5
    assert validate_market_provider_game_snapshot(snapshot)["snapshot_valid"] is True


def test_legacy_document_builds_step11a_snapshot():
    snapshot = normalize(legacy_document())
    assert snapshot["market_count"] == 3
    assert snapshot["markets"]["moneyline"]["away_odds"] == 110
    assert snapshot["markets"]["total"]["line"] == 9.0
    assert validate_market_provider_game_snapshot(snapshot)["snapshot_valid"] is True


def test_inplay_document_supported():
    snapshot = normalize(modern_document(in_play=True), phase="IN_PLAY")
    assert snapshot["market_phase"] == "IN_PLAY"
    assert snapshot["fully_priced"] is True


def test_missing_market_is_omitted_not_fabricated():
    doc = modern_document()
    doc["markets"] = doc["markets"][:1]
    snapshot = normalize(doc)
    assert list(snapshot["markets"]) == ["moneyline"]
    assert snapshot["market_count"] == 1
    assert snapshot["fully_priced"] is False
    assert snapshot["price_fabrication_used"] is False


def test_same_inputs_are_deterministic():
    assert normalize() == normalize()


def test_payload_change_changes_snapshot_hash():
    first = normalize()
    doc = modern_document()
    doc["extra"] = "source changed"
    second = normalize(doc)
    assert first["source_payload_sha256"] != second["source_payload_sha256"]
    assert first["snapshot_sha256"] != second["snapshot_sha256"]


@pytest.mark.parametrize("bad", [True, False, 0, -1, 1.5, "777001", None])
def test_official_game_id_must_be_exact_positive_int(bad):
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(gamepk=bad)


@pytest.mark.parametrize("bad", ["", " ", None, 123, True])
def test_provider_event_id_must_be_string(bad):
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(event=bad)


@pytest.mark.parametrize("phase", ["LIVE", "pregame", "", None, 1])
def test_phase_fails_closed(phase):
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(phase=phase)


def test_exact_event_gamepk_mapping_required():
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(mapping={"other": GAMEPK})


def test_exact_event_gamepk_mapping_mismatch_rejected():
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(mapping={EVENT: GAMEPK + 1})


@pytest.mark.parametrize("mapping", [{}, {EVENT: True}, {EVENT: 0}, {EVENT: -3}, {EVENT: 1.2}, {EVENT: "777001"}, {"": GAMEPK}])
def test_invalid_event_gamepk_maps_rejected(mapping):
    with pytest.raises(MLBDraftKingsProviderError):
        resolve_event_gamepk_map(mapping)


def test_event_gamepk_map_from_environment():
    env = {DRAFTKINGS_EVENT_GAMEPK_MAP_ENV: json.dumps({EVENT: GAMEPK})}
    assert resolve_event_gamepk_map(env=env) == {EVENT: GAMEPK}


def test_event_gamepk_map_missing_environment_is_not_ready():
    with pytest.raises(MLBDraftKingsProviderNotReadyError):
        resolve_event_gamepk_map(env={})


@pytest.mark.parametrize("url", [
    "http://sportsbook.draftkings.com/api/x",
    "https://example.com/api/x",
    "https://draftkings.com/api/x#fragment",
    "https://user:pass@draftkings.com/api/x",
    "ftp://draftkings.com/api/x",
    "https://notdraftkings.com/api/x",
])
def test_url_allowlist_rejects_unsafe_urls(url):
    with pytest.raises(MLBDraftKingsProviderError):
        resolve_draftkings_urls([url])


def test_url_allowlist_accepts_draftkings_subdomain_and_dedupes():
    assert resolve_draftkings_urls([URL, URL]) == [URL]


def test_urls_from_environment():
    assert resolve_draftkings_urls(env={DRAFTKINGS_URLS_ENV: json.dumps([URL])}) == [URL]


def test_missing_urls_are_not_ready():
    with pytest.raises(MLBDraftKingsProviderNotReadyError):
        resolve_draftkings_urls(env={})


def test_describe_provider_is_read_only_and_not_ready_without_config():
    info = describe_draftkings_provider({})
    assert info["ready"] is False
    assert info["configured_url_count"] == 0
    assert info["configured_event_gamepk_count"] == 0
    assert info["authentication_used"] is False
    assert info["production_runtime_wiring"] is False


def test_describe_provider_ready_with_exact_config():
    info = describe_draftkings_provider({
        DRAFTKINGS_URLS_ENV: json.dumps([URL]),
        DRAFTKINGS_EVENT_GAMEPK_MAP_ENV: json.dumps({EVENT: GAMEPK}),
        DRAFTKINGS_TIMEOUT_ENV: "2.5",
    })
    assert info["ready"] is True
    assert info["request_timeout_seconds"] == 2.5


@pytest.mark.parametrize("timeout", ["0", "0.49", "61", "nan", "abc"])
def test_bad_timeout_configuration_fails_readiness(timeout):
    info = describe_draftkings_provider({
        DRAFTKINGS_URLS_ENV: json.dumps([URL]),
        DRAFTKINGS_EVENT_GAMEPK_MAP_ENV: json.dumps({EVENT: GAMEPK}),
        DRAFTKINGS_TIMEOUT_ENV: timeout,
    })
    assert info["ready"] is False


def test_team_name_cannot_substitute_for_machine_away_role():
    doc = modern_document()
    doc["selections"][0]["label"] = "Arizona Diamondbacks"
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(doc)


def test_run_line_mismatch_fails_closed():
    doc = modern_document()
    doc["selections"][3]["points"] = -2.5
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(doc)


def test_total_line_mismatch_fails_closed():
    doc = modern_document()
    doc["selections"][5]["points"] = 9.5
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(doc)


def test_total_negative_fails_closed():
    doc = modern_document()
    doc["selections"][4]["points"] = -8.5
    doc["selections"][5]["points"] = -8.5
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(doc)


@pytest.mark.parametrize("bad", [99, -99, 0, True, 100.5, "EVEN", None])
def test_malformed_moneyline_price_fails_closed(bad):
    doc = modern_document()
    doc["selections"][0]["oddsAmerican"] = bad
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(doc)


def test_duplicate_away_selection_fails_closed():
    doc = modern_document()
    doc["selections"].append({"id": "dupe", "marketId": "m-money", "side": "away", "oddsAmerican": 120})
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(doc)


def test_closed_core_markets_are_not_used():
    doc = modern_document()
    for market in doc["markets"]:
        market["status"] = "SUSPENDED"
    with pytest.raises(MLBDraftKingsProviderNotReadyError):
        normalize(doc)


def test_pregame_rejects_inplay_markets_by_omission():
    with pytest.raises(MLBDraftKingsProviderNotReadyError):
        normalize(modern_document(in_play=True), phase="PREGAME")


def test_inplay_rejects_explicit_pregame_markets_by_omission():
    with pytest.raises(MLBDraftKingsProviderNotReadyError):
        normalize(modern_document(in_play=False), phase="IN_PLAY")


def test_nonboolean_inplay_flag_fails_closed():
    doc = modern_document()
    doc["markets"][0]["inPlay"] = "false"
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(doc)


def test_future_source_timestamp_rejected():
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(collected="2026-09-01T17:31:00Z")


def test_naive_observation_timestamp_rejected():
    with pytest.raises(MLBDraftKingsProviderError):
        normalize(observed="2026-09-01T17:30:00")


class FakeResponse:
    def __init__(self, payload=None, status_code=200, invalid_json=False):
        self.payload = payload
        self.status_code = status_code
        self.invalid_json = invalid_json
        self.content = b"{}"
    def json(self):
        if self.invalid_json:
            raise ValueError("bad json")
        return self.payload


def test_collection_with_injected_requester_builds_shadow_snapshot_without_runtime_write():
    calls = []
    def requester(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(modern_document())
    result = collect_draftkings_provider_snapshots(
        market_phase="PREGAME",
        urls=[URL],
        event_gamepk_map={EVENT: GAMEPK},
        requester=requester,
        now_utc=datetime(2026, 9, 1, 17, 30, tzinfo=timezone.utc),
        env={},
    )
    assert len(calls) == 1
    assert result["snapshot_count"] == 1
    assert result["snapshots"][0]["official_game_id"] == GAMEPK
    assert result["team_name_matching_used"] is False
    assert result["fuzzy_matching_used"] is False
    assert result["synthetic_game_id_used"] is False
    assert result["price_fabrication_used"] is False
    assert result["production_runtime_wiring"] is False
    assert result["production_database_writes"] is False


def test_collection_dedupes_duplicate_url_before_request():
    calls = []
    def requester(url, **kwargs):
        calls.append(url)
        return FakeResponse(modern_document())
    result = collect_draftkings_provider_snapshots(
        market_phase="PREGAME", urls=[URL, URL], event_gamepk_map={EVENT: GAMEPK}, requester=requester,
        now_utc=datetime(2026, 9, 1, 17, 30, tzinfo=timezone.utc), env={}
    )
    assert calls == [URL]
    assert result["source_count"] == 1
    assert result["snapshot_count"] == 1


def test_unmapped_provider_event_creates_no_snapshot_and_no_guess():
    doc = modern_document()
    doc["events"][0]["id"] = "unmapped"
    for market in doc["markets"]:
        market["eventId"] = "unmapped"
    result = collect_draftkings_provider_snapshots(
        market_phase="PREGAME", urls=[URL], event_gamepk_map={EVENT: GAMEPK}, requester=lambda *a, **k: FakeResponse(doc),
        now_utc=datetime(2026, 9, 1, 17, 30, tzinfo=timezone.utc), env={}
    )
    assert result["snapshot_count"] == 0
    assert result["source_summaries"][0]["mapped_event_count"] == 0


def test_http_error_fails_closed():
    with pytest.raises(MLBDraftKingsProviderUpstreamError):
        collect_draftkings_provider_snapshots(
            market_phase="PREGAME", urls=[URL], event_gamepk_map={EVENT: GAMEPK}, requester=lambda *a, **k: FakeResponse({}, 503), env={}
        )


def test_invalid_json_fails_closed():
    with pytest.raises(MLBDraftKingsProviderUpstreamError):
        collect_draftkings_provider_snapshots(
            market_phase="PREGAME", urls=[URL], event_gamepk_map={EVENT: GAMEPK}, requester=lambda *a, **k: FakeResponse(invalid_json=True), env={}
        )


def test_nonobject_json_fails_closed():
    with pytest.raises(MLBDraftKingsProviderUpstreamError):
        collect_draftkings_provider_snapshots(
            market_phase="PREGAME", urls=[URL], event_gamepk_map={EVENT: GAMEPK}, requester=lambda *a, **k: FakeResponse([]), env={}
        )


def test_naive_now_rejected():
    with pytest.raises(MLBDraftKingsProviderError):
        collect_draftkings_provider_snapshots(
            market_phase="PREGAME", urls=[URL], event_gamepk_map={EVENT: GAMEPK}, requester=lambda *a, **k: FakeResponse(modern_document()),
            now_utc=datetime(2026, 9, 1, 17, 30), env={}
        )


def test_unknown_markets_are_ignored_not_guessed():
    doc = modern_document()
    doc["markets"].append({"id": "weird", "eventId": EVENT, "name": "First Five Innings Moneyline", "status": "OPEN", "inPlay": False})
    snapshot = normalize(doc)
    assert snapshot["market_count"] == 3
    assert "weird" not in json.dumps(snapshot)
