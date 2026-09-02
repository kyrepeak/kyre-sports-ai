from __future__ import annotations

import json

import pytest

from sports_api.collectors import wnba_draftkings_direct as frozen_dk
import sports_api.wnba_reconciled_direct_sync as step6i
import sports_api.wnba_step6d_direct_integration as step6d
import sports_api.wnba_step19a_draftkings_sportscontent as step19a


class FakeResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code
        self.content = json.dumps(body).encode("utf-8")

    def json(self):
        return self._body


def _league_document():
    categories = [
        {"id": "1215", "name": "Player Points"},
        {"id": "1216", "name": "Player Rebounds"},
        {"id": "1217", "name": "Player Assists"},
        {"id": "583", "name": "Player Combos"},
    ]
    subcategories = [
        {"id": "12488", "categoryId": "1215", "name": "Points O/U"},
        {"id": "12492", "categoryId": "1216", "name": "Rebounds O/U"},
        {"id": "12495", "categoryId": "1217", "name": "Assists O/U"},
        {"id": "5001", "categoryId": "583", "name": "Pts + Reb + Ast O/U"},
    ]
    return {"categories": categories, "subcategories": subcategories}


def _market_document(stat):
    labels = {
        "points": "Test Player Points",
        "rebounds": "Test Player Rebounds",
        "assists": "Test Player Assists",
        "pra": "Test Player Points + Rebounds + Assists",
    }
    lines = {"points": 20.5, "rebounds": 7.5, "assists": 5.5, "pra": 33.5}
    market_id = f"market-{stat}"
    return {
        "events": [
            {
                "id": "event-1",
                "name": "New York Liberty @ Indiana Fever",
                "participants": [
                    {"name": "New York Liberty", "venueRole": "Away"},
                    {"name": "Indiana Fever", "venueRole": "Home"},
                ],
                "startEventDate": "2026-08-29T23:00:00Z",
            }
        ],
        "markets": [
            {
                "id": market_id,
                "eventId": "event-1",
                "name": labels[stat],
            }
        ],
        "selections": [
            {
                "id": f"{stat}-over",
                "marketId": market_id,
                "playerName": "Test Player",
                "label": "Over",
                "points": lines[stat],
                "displayOdds": {"american": "-110"},
            },
            {
                "id": f"{stat}-under",
                "marketId": market_id,
                "playerName": "Test Player",
                "label": "Under",
                "points": lines[stat],
                "displayOdds": {"american": "-110"},
            },
        ],
    }


def _requester(url, **kwargs):
    assert kwargs.get("timeout")
    assert "sportsbook-nash.draftkings.com" in url
    if url.endswith("/leagues/94682"):
        return FakeResponse(_league_document())
    if "/1215/subcategories/12488" in url:
        return FakeResponse(_market_document("points"))
    if "/1216/subcategories/12492" in url:
        return FakeResponse(_market_document("rebounds"))
    if "/1217/subcategories/12495" in url:
        return FakeResponse(_market_document("assists"))
    if "/583/subcategories/5001" in url:
        return FakeResponse(_market_document("pra"))
    raise AssertionError(f"unexpected URL: {url}")


def test_disabled_status_preserves_frozen_step6d_contract():
    env = {}
    observed = step19a.describe_step19a_draftkings_onboarding(env)
    expected = step19a._ORIGINAL_DESCRIBE(env)
    assert observed == expected
    assert observed["ready"] is False
    assert observed["secret_required"] is False


def test_enabled_status_requires_no_old_urls_or_provider_secret():
    env = {step19a.STEP19A_ENABLED_ENV: "true"}
    status = step19a.describe_step19a_draftkings_onboarding(env)
    assert status["ready"] is True
    assert status["configured_url_count"] == 4
    assert status["secret_required"] is False
    assert status["authentication_used"] is False
    assert status["dynamic_market_discovery"] is True
    assert status["target_stats"] == ["points", "rebounds", "assists", "pra"]
    assert frozen_dk.DRAFTKINGS_URLS_ENV not in env


def test_site_is_fail_closed_to_certified_jurisdictions():
    env = {
        step19a.STEP19A_ENABLED_ENV: "true",
        step19a.STEP19A_SITE_ENV: "dkusxx",
    }
    status = step19a.describe_step19a_draftkings_onboarding(env)
    assert status["ready"] is False
    assert step19a.STEP19A_SITE_ENV in status["configuration_error"]
    with pytest.raises(frozen_dk.WNBADraftKingsDirectModelInputError):
        step19a.build_step19a_draftkings_snapshot(
            date="2026-08-29", season=2026, env=env, requester=_requester
        )


def test_build_snapshot_reuses_frozen_normalizer_for_all_four_prop_families():
    env = {step19a.STEP19A_ENABLED_ENV: "true"}
    snapshot = step19a.build_step19a_draftkings_snapshot(
        date="2026-08-29", season=2026, env=env, requester=_requester
    )
    assert snapshot["schema_version"] == "wnba_step_6c_owned_market_feed_v1"
    assert snapshot["feed_format"] == "canonical_offers_v1"
    assert snapshot["odds_format"] == "american"
    assert snapshot["date"] == "2026-08-29"
    assert snapshot["season"] == 2026
    assert len(snapshot["source_events"]) == 1
    assert snapshot["source_events"][0]["source_event_id"] == "event-1"
    assert set(snapshot["source_events"][0]["participants"]) == {
        "New York Liberty",
        "Indiana Fever",
    }
    offers = snapshot["offers"]
    assert len(offers) == 8
    assert {row["stat"] for row in offers} == {"points", "rebounds", "assists", "pra"}
    for stat in ("points", "rebounds", "assists", "pra"):
        rows = [row for row in offers if row["stat"] == stat]
        assert {row["side"] for row in rows} == {"over", "under"}
        assert all(row["sportsbook"] == "DraftKings" for row in rows)
        assert all(row["player_name"] == "Test Player" for row in rows)
        assert all(row["american_odds"] == -110 for row in rows)
    assert snapshot["step19a"]["provider_api_key_used"] is False
    assert snapshot["step19a"]["stat_counts"] == {
        "points": 2,
        "rebounds": 2,
        "assists": 2,
        "pra": 2,
    }


def test_verified_snapshot_delegates_when_step19a_disabled(monkeypatch):
    sentinel = {"source": "frozen-step6h"}

    def frozen_delegate(*, date, season, env):
        assert date == "2026-08-29"
        assert season == 2026
        assert env == {}
        return sentinel

    monkeypatch.setattr(step19a, "_ORIGINAL_FETCH_VERIFIED", frozen_delegate)
    assert (
        step19a.fetch_verified_draftkings_snapshot_step19a(
            date="2026-08-29", season=2026, env={}
        )
        is sentinel
    )


def test_installation_patches_only_existing_step6d_step6i_runtime_seams():
    result = step19a.install_step19a_sportscontent_transport()
    assert result["installed"] is True
    assert result["frozen_step6d_source_modified"] is False
    assert result["frozen_step6i_source_modified"] is False
    assert result["provider_api_key_required"] is False
    assert step6d.describe_draftkings_direct_onboarding is step19a.describe_step19a_draftkings_onboarding
    assert step6i.fetch_verified_draftkings_snapshot is step19a.fetch_verified_draftkings_snapshot_step19a


def test_step6d_status_can_become_ready_without_legacy_url_env():
    env = {
        step19a.STEP19A_ENABLED_ENV: "true",
        step6d.DIRECT_SYNC_ENABLED_ENV: "true",
        step6d.DIRECT_SYNC_PROVIDER_ENV: "draftkings",
    }
    step19a.install_step19a_sportscontent_transport()
    status = step6d.get_step6d_direct_market_status(env)
    assert status["direct_sync_enabled"] is True
    assert status["direct_sync_active"] is True
    assert status["draftkings"]["ready"] is True
    assert status["draftkings"]["secret_required"] is False
    assert frozen_dk.DRAFTKINGS_URLS_ENV not in env
