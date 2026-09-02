from __future__ import annotations

import json

from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step19h_fanduel_hosted_transport as step19h


class FakeResponse:
    def __init__(self, *, status_code=200, content=b"{}", headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = dict(headers or {})

    def json(self):
        return json.loads(self.content.decode("utf-8"))


def test_response_metadata_classifies_html_without_logging_body_or_query():
    url = (
        "https://api.sportsbook.fanduel.com/sbapi/event-page"
        "?_ak=PUBLICKEY&eventId=123&tab=player-points"
    )
    response = FakeResponse(
        content=b"   <html><title>blocked</title></html>",
        headers={"content-type": "text/html", "content-length": "42", "set-cookie": "secret=1"},
    )
    event = step19h._response_event(url, response)
    assert event["status_code"] == 200
    assert event["content_type"] == "text/html"
    assert event["body_shape"] == "markup_or_html"
    assert event["json_decodable"] is False
    assert event["body_captured"] is False
    assert event["query_captured"] is False
    serialized = repr(event)
    assert "blocked" not in serialized
    assert "PUBLICKEY" not in serialized
    assert "eventId" not in serialized
    assert "set-cookie" not in serialized
    assert "secret=1" not in serialized


def test_response_metadata_classifies_valid_json_without_retaining_payload():
    response = FakeResponse(
        content=b'{"attachments":{"markets":{"private_payload":"never log me"}}}',
        headers={"content-type": "application/json"},
    )
    event = step19h._response_event(
        "https://api.sportsbook.fanduel.com/sbapi/content-managed-page?customPageId=wnba",
        response,
    )
    assert event["body_shape"] == "json_object"
    assert event["json_decodable"] is True
    assert event["body_byte_length"] > 0
    assert len(event["body_sha256"]) == 64
    assert "private_payload" not in repr(event)
    assert "never log me" not in repr(event)


def test_wrapper_injects_probe_only_when_default_requester_would_be_used():
    original = step19h._ORIGINAL_FETCH_STEP11C
    observed = []

    def fake_fetch(**kwargs):
        observed.append(kwargs.get("requester"))
        return {"unchanged": True}

    explicit = lambda *args, **kwargs: None
    try:
        step19h._ORIGINAL_FETCH_STEP11C = fake_fetch
        result_default = step19h.fetch_step11c_with_transport_probe(
            season=2026, slate_date="2026-08-29"
        )
        result_explicit = step19h.fetch_step11c_with_transport_probe(
            season=2026, slate_date="2026-08-29", requester=explicit
        )
    finally:
        step19h._ORIGINAL_FETCH_STEP11C = original

    assert result_default == {"unchanged": True}
    assert result_explicit == {"unchanged": True}
    assert observed[0] is step19h.diagnostic_requester
    assert observed[1] is explicit


def test_install_keeps_frozen_semantics_and_installs_fetch_wrapper():
    status = step19h.install_step19h_fanduel_hosted_transport()
    assert status["installed"] is True
    assert fanduel.fetch_step11c_fanduel_provider_bridge is step19h.fetch_step11c_with_transport_probe
    assert status["request_method_changed"] is False
    assert status["redirect_policy_changed"] is False
    assert status["authentication_added"] is False
    assert status["cookies_added"] is False
    assert status["readiness_relaxed"] is False
    assert status["provider_retry_policy_modified"] is False
    assert status["projection_logic_modified"] is False
    assert status["controller_state_modified"] is False
    assert status["response_body_logged"] is False
    assert status["query_logged"] is False
    assert status["wagering_enabled"] is False


def test_public_status_contains_metadata_only():
    step19h._clear_for_test()
    event = step19h._response_event(
        "https://api.sportsbook.fanduel.com/sbapi/event-page?eventId=secret-id",
        FakeResponse(content=b"not-json", headers={"content-type": "text/plain"}),
    )
    step19h._append(event)
    status = step19h.get_step19h_fanduel_transport_status()
    assert status["captured_event_count"] == 1
    assert status["invalid_json_event_count"] == 1
    assert status["events"][0]["path"] == "/sbapi/event-page"
    assert "secret-id" not in repr(status)
    assert status["guardrails"]["metadata_only"] is True
    assert status["guardrails"]["response_body_logged"] is False
    assert status["guardrails"]["query_logged"] is False
