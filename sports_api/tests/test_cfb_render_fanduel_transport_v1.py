from __future__ import annotations

import json

import pytest

from sports_api.api import cfb_markets as frozen_markets
from sports_api.api import cfb_render_fanduel_transport_v1 as overlay
from sports_api.collectors import cfb_fanduel_hosted_transport_v1 as hosted


class _FakeResponse:
    status = 200

    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _limit: int) -> bytes:
        return self._raw


def test_hosted_transport_is_one_anonymous_get(monkeypatch):
    calls = []
    payload = {"attachments": {"events": {}, "markets": {}}}

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return _FakeResponse(payload)

    monkeypatch.setattr(hosted, "urlopen", fake_urlopen)
    result = hosted.fetch_fanduel_ncaaf_page_hosted(timeout=7.0)

    assert result == payload
    assert len(calls) == 1
    request, timeout = calls[0]
    assert request.get_method() == "GET"
    assert timeout == 7.0
    assert "customPageId=ncaaf" in request.full_url
    assert "page=CUSTOM" in request.full_url
    assert "_ak=" in request.full_url


def test_overlay_reuses_frozen_normalizer_and_store(monkeypatch):
    source = {
        "schema_version": "cfb_market_feed_v1",
        "captured_at_utc": "2026-09-10T20:00:00+00:00",
        "source": "FanDuel anonymous public NCAAF content-managed-page",
        "games": [],
    }
    validated = {**source, "market_semantics": {"projection_weight": 0.0}}
    seen = {}

    def fake_collect(*, page_fetcher):
        seen["page_fetcher"] = page_fetcher
        return source

    def fake_validate(payload):
        seen["validated_input"] = payload
        return validated

    def fake_store(payload):
        seen["stored"] = payload

    monkeypatch.setattr(overlay, "collect_fanduel_cfb_total_feed", fake_collect)
    monkeypatch.setattr(frozen_markets, "validate_feed", fake_validate)
    monkeypatch.setattr(frozen_markets, "_store_validated_feed", fake_store)

    result = overlay._refresh_from_fanduel_hosted()

    assert result is validated
    assert seen["page_fetcher"] is overlay.fetch_fanduel_ncaaf_page_hosted
    assert seen["validated_input"] is source
    assert seen["stored"] is validated
    assert overlay.PROJECTION_WEIGHT == 0.0
    assert overlay.MAY_MODIFY_PROJECTION is False


def test_install_changes_only_refresh_seam(monkeypatch):
    original_load = frozen_markets._load_feed
    original_validate = frozen_markets.validate_feed
    original_store = frozen_markets._store_validated_feed

    monkeypatch.setattr(
        frozen_markets,
        "_refresh_from_fanduel",
        lambda: {"before": True},
    )
    overlay.install_hosted_transport()

    assert frozen_markets._refresh_from_fanduel is overlay._refresh_from_fanduel_hosted
    assert frozen_markets._load_feed is original_load
    assert frozen_markets.validate_feed is original_validate
    assert frozen_markets._store_validated_feed is original_store


def test_hosted_transport_rejects_non_object_json(monkeypatch):
    class _ListResponse(_FakeResponse):
        def __init__(self):
            self._raw = b"[]"

    monkeypatch.setattr(hosted, "urlopen", lambda request, timeout: _ListResponse())

    with pytest.raises(Exception, match="not a JSON object"):
        hosted.fetch_fanduel_ncaaf_page_hosted()
