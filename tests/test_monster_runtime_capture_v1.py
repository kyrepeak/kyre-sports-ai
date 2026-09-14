from __future__ import annotations

import json
from pathlib import Path

import pytest

from sports_api.monster_runtime_capture_v1 import (
    CAPTURE_VERSION,
    ReplayArtifact,
    artifact_from_dict,
    capture_response,
    read_artifact,
    session_from_artifacts,
    write_artifact,
)


def test_capture_strips_query_and_redacts_sensitive_fields():
    artifact = capture_response(
        route_key="cfb_odds",
        url="https://api.test/api/v1/cfb/odds?token=secret&date=2026-09-14",
        status_code=503,
        headers={
            "X-Request-ID": "req-503",
            "Authorization": "Bearer hidden",
            "Content-Type": "application/json",
            "X-Kyre-Deploy-Commit": "abc123",
        },
        params={"token": "secret", "date": "2026-09-14"},
        json_body={"detail": "protected", "api_key": "hidden"},
    )
    payload = artifact.as_dict()
    assert payload["version"] == CAPTURE_VERSION
    assert payload["url"] == "https://api.test/api/v1/cfb/odds"
    assert "Authorization" not in payload["headers"]
    assert payload["headers"]["X-Request-ID"] == "req-503"
    assert payload["params"]["token"] == "<redacted>"
    assert payload["json_body"]["api_key"] == "<redacted>"


def test_capture_strips_http_userinfo_credentials_from_url():
    artifact = capture_response(
        route_key="userinfo",
        url="https://user:super-secret@example.com:8443/path?token=also-secret#fragment",
        status_code=200,
        json_body={"status": "ok"},
    )
    assert artifact.url == "https://example.com:8443/path"
    serialized = json.dumps(artifact.as_dict())
    assert "user" not in artifact.url
    assert "super-secret" not in serialized
    assert "also-secret" not in serialized


def test_capture_recursively_redacts_scalar_and_nested_sequence_credentials():
    artifact = capture_response(
        route_key="nested-secrets",
        url="https://api.test/nested",
        status_code=200,
        json_body=[
            "Bearer top-secret",
            ["Basic dXNlcjpwYXNz", {"token": "nested-token", "safe": "ok"}],
            {"items": ["Bearer another-secret", {"password": "hidden"}]},
        ],
        note="Bearer note-secret",
    )
    body = artifact.json_body
    assert body[0] == "<redacted>"
    assert body[1][0] == "<redacted>"
    assert body[1][1]["token"] == "<redacted>"
    assert body[1][1]["safe"] == "ok"
    assert body[2]["items"][0] == "<redacted>"
    assert body[2]["items"][1]["password"] == "<redacted>"
    assert artifact.note == "<redacted>"


def test_artifact_has_stable_fingerprint_for_same_sanitized_exchange():
    kwargs = dict(
        route_key="route",
        url="https://api.test/route",
        status_code=200,
        headers={"X-Request-ID": "req-1"},
        params={"event_id": "401"},
        json_body={"status": "ok", "games": []},
    )
    one = capture_response(**kwargs)
    two = capture_response(**kwargs)
    assert one.fingerprint == two.fingerprint
    assert one.fingerprint.startswith("REPLAY-")


def test_write_read_round_trip_and_replay(tmp_path: Path):
    artifact = capture_response(
        route_key="cfb_odds",
        url="https://api.test/api/v1/cfb/odds",
        status_code=503,
        headers={"X-Request-ID": "req-503"},
        json_body={"detail": "CFB odds endpoint is not ready: market identity coverage is incomplete"},
    )
    path = write_artifact(tmp_path / "cfb-503.json", artifact)
    loaded = read_artifact(path)
    assert loaded == artifact
    session = session_from_artifacts(loaded)
    response = session.get("https://api.test/api/v1/cfb/odds")
    assert response.status_code == 503
    assert response.json()["detail"].startswith("CFB odds endpoint")


def test_artifact_from_dict_fails_closed_on_unknown_version():
    with pytest.raises(ValueError, match="Unsupported replay artifact version"):
        artifact_from_dict({"version": "future", "route_key": "x"})


def test_artifact_size_limit_fails_closed():
    # Scalar strings are intentionally clipped by the sanitizer before storage,
    # so exercise the total artifact cap with many individually safe fields.
    huge = {f"field_{index:04d}": "x" * 160 for index in range(3000)}
    with pytest.raises(ValueError, match="size limit"):
        capture_response(
            route_key="huge",
            url="https://api.test/huge",
            status_code=200,
            json_body=huge,
        )


def test_timeout_artifact_can_be_replayed():
    artifact = capture_response(
        route_key="slow",
        url="https://api.test/slow",
        status_code=200,
        json_body={"status": "late"},
        timeout=True,
    )
    session = session_from_artifacts(artifact)
    import requests

    with pytest.raises(requests.Timeout):
        session.get("https://api.test/slow")


def test_as_dict_declares_read_only_safety():
    artifact = ReplayArtifact(
        route_key="safe",
        method="GET",
        url="https://api.test/safe",
        status_code=200,
        headers={},
        params={},
        json_body={"status": "ok"},
    )
    payload = artifact.as_dict()
    assert payload["projection_weight"] == 0.0
    assert payload["may_modify_projection"] is False
    assert payload["may_modify_source_data"] is False
    assert payload["network_calls"] is False
    json.dumps(payload)
