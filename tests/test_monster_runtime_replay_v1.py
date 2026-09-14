from __future__ import annotations

import requests
import pytest

from sports_api.monster_runtime_replay_v1 import (
    CFB_PROTECTED_503_DETAIL,
    NETWORK_CALLS,
    PROJECTION_WEIGHT,
    ReplaySession,
    ResponseFixture,
    body_aware_json_helper,
    canonical_http_scenarios,
    legacy_json_helper,
    sanitize_mapping,
)


def test_canonical_scenarios_cover_required_runtime_failures():
    scenarios = canonical_http_scenarios()
    assert set(scenarios) == {
        "200",
        "404",
        "429",
        "500",
        "502",
        "503",
        "timeout",
        "malformed_json",
    }


@pytest.mark.parametrize("name,status", [("200", 200), ("404", 404), ("429", 429), ("500", 500), ("502", 502), ("503", 503)])
def test_replay_returns_exact_registered_status(name, status):
    session = ReplaySession()
    session.register("https://runtime.test/route", canonical_http_scenarios()[name])
    response = session.get("https://runtime.test/route")
    assert response.status_code == status
    assert session.receipt()["exchanges"][0]["status_code"] == status


def test_timeout_is_replayed_without_network_call():
    session = ReplaySession()
    session.register("https://runtime.test/route", canonical_http_scenarios()["timeout"])
    with pytest.raises(requests.Timeout):
        session.get("https://runtime.test/route")
    receipt = session.receipt()
    assert receipt["exchanges"][0]["outcome"] == "timeout"
    assert NETWORK_CALLS is False


def test_malformed_json_is_replayed_exactly():
    session = ReplaySession()
    session.register("https://runtime.test/route", canonical_http_scenarios()["malformed_json"])
    response = session.get("https://runtime.test/route")
    with pytest.raises(ValueError, match="malformed JSON"):
        response.json()


def test_legacy_helper_reproduces_the_pre_440_503_failure_mechanism():
    session = ReplaySession()
    session.register(
        "https://runtime.test/api/v1/cfb/odds",
        canonical_http_scenarios()["503"],
    )
    with pytest.raises(requests.HTTPError) as captured:
        legacy_json_helper(session, "https://runtime.test/api/v1/cfb/odds")
    assert captured.value.response is not None
    assert captured.value.response.status_code == 503
    assert CFB_PROTECTED_503_DETAIL in captured.value.response.text


def test_body_aware_helper_preserves_exact_protected_503_for_contract_inspection():
    session = ReplaySession()
    session.register(
        "https://runtime.test/api/v1/cfb/odds",
        canonical_http_scenarios()["503"],
    )
    status, payload = body_aware_json_helper(session, "https://runtime.test/api/v1/cfb/odds")
    assert status == 503
    assert payload == {"detail": CFB_PROTECTED_503_DETAIL}


def test_replay_can_return_sequence_for_retries_or_state_change():
    session = ReplaySession()
    session.register(
        "https://runtime.test/route",
        ResponseFixture(503, {"detail": "warming"}),
        ResponseFixture(200, {"status": "ok"}),
    )
    assert session.get("https://runtime.test/route").status_code == 503
    assert session.get("https://runtime.test/route").status_code == 200
    assert [row.status_code for row in session.exchanges] == [503, 200]


def test_sensitive_headers_params_and_body_keys_are_redacted():
    session = ReplaySession()
    session.register(
        "https://runtime.test/route",
        ResponseFixture(
            200,
            {
                "status": "ok",
                "api_key": "do-not-store",
                "nested": {"token": "also-secret", "count": 2},
            },
            headers={
                "X-Request-ID": "req-123",
                "Authorization": "Bearer very-secret",
                "Set-Cookie": "session=secret",
            },
        ),
    )
    session.get("https://runtime.test/route", params={"token": "secret", "event_id": "401"})
    row = session.receipt()["exchanges"][0]
    assert row["request_id"] == "req-123"
    assert row["headers"]["Authorization"] == "<redacted>"
    assert row["headers"]["Set-Cookie"] == "<redacted>"
    assert row["params"]["token"] == "<redacted>"
    assert row["params"]["event_id"] == "401"
    assert row["body_shape"]["api_key"] == "<redacted>"
    assert row["body_shape"]["nested"]["token"] == "<redacted>"


def test_runtime_replay_is_measurement_only():
    assert PROJECTION_WEIGHT == 0.0
    assert NETWORK_CALLS is False
    sanitized = sanitize_mapping({"Authorization": "Bearer x", "safe": "ok"})
    assert sanitized == {"Authorization": "<redacted>", "safe": "ok"}
