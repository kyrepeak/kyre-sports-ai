from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step19h_fanduel_hosted_transport as step19h
from sports_api import wnba_step19i_official_slate_transport as step19i


def _schedule(*, season: str = "2026") -> dict:
    return {
        "leagueSchedule": {
            "leagueId": "10",
            "seasonYear": season,
            "gameDates": [
                {
                    "gameDate": "2026-08-30",
                    "games": [
                        {
                            "gameId": "1022600301",
                            "homeTeam": {
                                "teamId": "1611661319",
                                "teamCity": "Las Vegas",
                                "teamName": "Aces",
                                "teamTricode": "LVA",
                            },
                            "awayTeam": {
                                "teamId": "1611661325",
                                "teamCity": "Indiana",
                                "teamName": "Fever",
                                "teamTricode": "IND",
                            },
                        }
                    ],
                }
            ],
        }
    }


class _Response:
    status_code = 200
    content = b"{}"

    def __init__(self, payload: dict):
        self._payload = deepcopy(payload)

    def json(self):
        return deepcopy(self._payload)


def test_installation_changes_only_step11c_official_schedule_transport():
    status = step19i.install_step19i_official_slate_transport()
    assert status["installed"] is True
    assert status["official_schedule_transport_active"] is True
    assert fanduel._get_json is step19i.fanduel_get_json_step19i
    assert status["sportsbook_transport_modified"] is False
    assert status["official_identity_parser_modified"] is False
    assert status["readiness_relaxed"] is False
    assert status["controller_state_modified"] is False
    assert status["projection_logic_modified"] is False
    assert status["wagering_enabled"] is False


def test_hosted_diagnostic_schedule_read_uses_certified_first_party_loader(monkeypatch):
    payload = _schedule()
    calls = []

    def loader(season: int):
        calls.append(season)
        return (
            deepcopy(payload),
            "2026-08-30T00:00:00+00:00",
            "wnba_com_first_party_schedule_proxy",
            "https://www.wnba.com/api/schedule?season=2026",
            False,
        )

    monkeypatch.setattr(step19i, "_FIRST_PARTY_SCHEDULE_LOADER", loader)
    result = step19i.fanduel_get_json_step19i(
        fanduel.OFFICIAL_SCHEDULE_URL,
        params=None,
        requester=step19h.diagnostic_requester,
        timeout=15.0,
    )
    assert result == payload
    assert calls == [2026]


def test_default_schedule_read_uses_certified_first_party_loader(monkeypatch):
    payload = _schedule()
    monkeypatch.setattr(
        step19i,
        "_FIRST_PARTY_SCHEDULE_LOADER",
        lambda season: (
            deepcopy(payload),
            "2026-08-30T00:00:00+00:00",
            "wnba_com_first_party_schedule_proxy",
            "https://www.wnba.com/api/schedule?season=2026",
            True,
        ),
    )
    assert step19i.fanduel_get_json_step19i(
        fanduel.OFFICIAL_SCHEDULE_URL,
        params=None,
        requester=None,
        timeout=15.0,
    ) == payload


def test_explicit_fixture_requester_preserves_frozen_step11c_behavior(monkeypatch):
    expected = _schedule()

    def should_not_load(_season: int):
        raise AssertionError("first-party loader should not replace explicit test requester")

    def requester(url, *, params, headers, timeout):
        assert url == fanduel.OFFICIAL_SCHEDULE_URL
        return _Response(expected)

    monkeypatch.setattr(step19i, "_FIRST_PARTY_SCHEDULE_LOADER", should_not_load)
    result = step19i.fanduel_get_json_step19i(
        fanduel.OFFICIAL_SCHEDULE_URL,
        params=None,
        requester=requester,
        timeout=15.0,
    )
    assert result == expected


def test_fanduel_sportsbook_get_still_delegates_to_frozen_transport():
    expected = {"attachments": {}}

    def requester(url, *, params, headers, timeout):
        assert url.startswith(fanduel.FANDUEL_BASE_URL)
        return _Response(expected)

    result = step19i.fanduel_get_json_step19i(
        fanduel.FANDUEL_BASE_URL + fanduel.CONTENT_PAGE_PATH,
        params={"page": "CUSTOM"},
        requester=requester,
        timeout=15.0,
    )
    assert result == expected


def test_invalid_or_wrong_season_first_party_payload_fails_closed(monkeypatch):
    bad = _schedule(season="2025")
    monkeypatch.setattr(
        step19i,
        "_FIRST_PARTY_SCHEDULE_LOADER",
        lambda season: (
            bad,
            "2026-08-30T00:00:00+00:00",
            "wnba_com_first_party_schedule_proxy",
            "https://www.wnba.com/api/schedule?season=2026",
            False,
        ),
    )
    with pytest.raises(fanduel.WNBAStep11FanDuelProviderUpstreamError):
        step19i.fanduel_get_json_step19i(
            fanduel.OFFICIAL_SCHEDULE_URL,
            params=None,
            requester=step19h.diagnostic_requester,
            timeout=15.0,
        )


def test_empty_schedule_fails_closed(monkeypatch):
    empty = {
        "leagueSchedule": {
            "leagueId": "10",
            "seasonYear": "2026",
            "gameDates": [],
        }
    }
    monkeypatch.setattr(
        step19i,
        "_FIRST_PARTY_SCHEDULE_LOADER",
        lambda season: (
            empty,
            "2026-08-30T00:00:00+00:00",
            "wnba_com_first_party_schedule_proxy",
            "https://www.wnba.com/api/schedule?season=2026",
            False,
        ),
    )
    with pytest.raises(fanduel.WNBAStep11FanDuelProviderUpstreamError):
        step19i._load_certified_first_party_schedule()
