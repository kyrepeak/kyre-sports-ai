from __future__ import annotations

import copy
import importlib
import sys
import types

import httpx

try:
    import requests  # type: ignore
except ModuleNotFoundError:
    requests = types.ModuleType("requests")

    class _HTTPError(Exception):
        pass

    class _Session:
        def get(self, *args, **kwargs):
            raise RuntimeError("requests.Session is unavailable in the Runless proof sandbox")

    requests.HTTPError = _HTTPError
    requests.Session = _Session
    sys.modules["requests"] = requests


ALIASES = {
    "NY": "NYK",
    "SA": "SAS",
    "WSH": "WAS",
    "NO": "NOP",
    "GS": "GSW",
    "UTAH": "UTA",
}


def _espn_payload(away_code: object, home_code: object = "BOS") -> dict:
    return {
        "events": [
            {
                "id": "alias-test",
                "date": "2026-10-16T02:00:00Z",
                "status": {"type": {"state": "pre", "description": "Scheduled"}},
                "competitions": [
                    {
                        "date": "2026-10-16T02:00:00Z",
                        "venue": {"fullName": "Test Arena"},
                        "competitors": [
                            {
                                "homeAway": "away",
                                "team": {
                                    "abbreviation": away_code,
                                    "displayName": "Away Team",
                                },
                            },
                            {
                                "homeAway": "home",
                                "team": {
                                    "abbreviation": home_code,
                                    "displayName": "Boston Celtics",
                                },
                            },
                        ],
                    }
                ],
            }
        ]
    }


def _official_payload() -> dict:
    return {
        "leagueSchedule": {
            "gameDates": [
                {
                    "gameDate": "10/15/2026 00:00:00",
                    "games": [
                        {
                            "gameId": "0012600101",
                            "gameDateTimeUTC": "2026-10-16T02:00:00Z",
                            "gameStatus": 1,
                            "gameStatusText": "Scheduled",
                            "arenaName": "Madison Square Garden",
                            "awayTeam": {
                                "teamTricode": "BOS",
                                "teamCity": "Boston",
                                "teamName": "Celtics",
                            },
                            "homeTeam": {
                                "teamTricode": "NYK",
                                "teamCity": "New York",
                                "teamName": "Knicks",
                            },
                        }
                    ],
                }
            ]
        }
    }


class _HttpxSession:
    def __init__(self) -> None:
        self._client = httpx.Client(follow_redirects=True)

    def get(self, url, *args, params=None, headers=None, timeout=None):
        wire_headers = dict(headers or {})
        if "Accept-Encoding" in wire_headers:
            wire_headers["Accept-Encoding"] = "gzip, deflate"
        return self._client.get(url, params=params, headers=wire_headers, timeout=timeout)


def test_step1_normalizes_every_known_espn_alias_before_frozen_parse():
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    frozen = transport.frozen_schedule

    for espn_code, nba_code in ALIASES.items():
        normalized = transport._normalize_espn_team_aliases(_espn_payload(espn_code))
        abbreviation = normalized["events"][0]["competitions"][0]["competitors"][0]["team"]["abbreviation"]
        assert abbreviation == nba_code

        parsed = frozen.parse_espn(normalized, ("2026-10-15",))
        assert len(parsed) == 1
        assert parsed[0]["away_tricode"] == nba_code
        assert parsed[0]["source"] == "ESPN NBA"


def test_step1_unknown_espn_alias_is_not_guessed_and_fails_closed():
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    frozen = transport.frozen_schedule
    payload = _espn_payload("XYZ")

    normalized = transport._normalize_espn_team_aliases(payload)
    abbreviation = normalized["events"][0]["competitions"][0]["competitors"][0]["team"]["abbreviation"]
    assert abbreviation == "XYZ"
    assert frozen.parse_espn(normalized, ("2026-10-15",)) == []


def test_step1_malformed_espn_identity_remains_fail_closed():
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    frozen = transport.frozen_schedule

    normalized = transport._normalize_espn_team_aliases(_espn_payload(None))
    assert frozen.parse_espn(normalized, ("2026-10-15",)) == []


def test_step1_alias_normalizer_does_not_touch_nba_official_payloads():
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    payload = _official_payload()
    before = copy.deepcopy(payload)

    assert transport._normalize_espn_team_aliases(payload) == before
    assert payload == before


def test_step1_alias_normalization_preserves_exact_two_source_quorum():
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    frozen = transport.frozen_schedule
    window = ("2026-10-15",)

    official = frozen.parse_nba_official(_official_payload(), window)
    espn_payload = _espn_payload("BOS", "NY")
    espn = frozen.parse_espn(transport._normalize_espn_team_aliases(espn_payload), window)
    result = frozen.reconcile_verified_schedule(official, espn, window)

    assert result["verification"] == "VERIFIED"
    assert result["diagnostic_state"] == "SOURCE_CONSENSUS"
    assert result["source_agreement"] == 2
    assert result["games"][0]["confirming_sources"] == ["NBA Official", "ESPN NBA"]


def test_step1_live_alias_normalization_provider_identity_counts():
    """Live certification: providers must normalize to the same non-empty key set."""
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    frozen = transport.frozen_schedule
    repaired = transport._NbaProviderTransportRepairSession(
        _HttpxSession(),
        season_start_year=transport._season_start_year(None),
    )
    window = frozen.rolling_phoenix_dates(days=7)

    official_payload = frozen._fetch_official(repaired, timeout=12.0)
    espn_payload = frozen._fetch_espn(repaired, window, timeout=12.0)
    official_games = frozen.parse_nba_official(official_payload, window)
    espn_games = frozen.parse_espn(espn_payload, window)
    official_keys = {game["game_key"] for game in official_games}
    espn_keys = {game["game_key"] for game in espn_games}
    official_only_keys = sorted(official_keys - espn_keys)
    espn_only_keys = sorted(espn_keys - official_keys)

    print(f"official_game_count={len(official_games)}")
    print(f"espn_game_count={len(espn_games)}")
    print(f"official_only_keys={official_only_keys}")
    print(f"espn_only_keys={espn_only_keys}")

    assert official_games
    assert len(official_games) == len(espn_games)
    assert official_only_keys == []
    assert espn_only_keys == []

    result = frozen.reconcile_verified_schedule(official_games, espn_games, window)
    assert result["verification"] == "VERIFIED"
    assert result["diagnostic_state"] == "SOURCE_CONSENSUS"
    assert result["source_agreement"] == 2
    assert all(
        game["confirming_sources"] == ["NBA Official", "ESPN NBA"]
        for game in result["games"]
    )
