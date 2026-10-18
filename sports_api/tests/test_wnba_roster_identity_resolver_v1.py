from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import inspect
import json

import pytest

from sports_api.wnba_rosters import WNBAStatsUpstreamError
from sports_api.wnba_prop_line_feed_adapter import build_prop_line_feed_board


NOW = datetime(2026, 10, 18, 18, 40, tzinfo=timezone.utc)
PLAYABLE_GAMES = [
    {
        "game_id": "401999001",
        "away": {"team_key": "dream", "full_name": "Atlanta Dream", "team_tricode": "ATL"},
        "home": {"team_key": "valkyries", "full_name": "Golden State Valkyries", "team_tricode": "GSV"},
        "verification": {"playable_pregame": True},
    }
]
OFFICIAL_PLAYERS = [
    {
        "player_id": 101,
        "full_name": "Allisha Gray",
        "display_last_comma_first": "Gray, Allisha",
        "team_key": "dream",
        "is_current_roster": True,
    },
    {
        "player_id": 102,
        "full_name": "Rhyne Howard",
        "display_last_comma_first": "Howard, Rhyne",
        "team_key": "dream",
        "is_current_roster": True,
    },
    {
        "player_id": 201,
        "full_name": "Veronica Burton",
        "display_last_comma_first": "Burton, Veronica",
        "team_key": "valkyries",
        "is_current_roster": True,
    },
]


class MemoryStorage:
    backend_id = "memory"

    def __init__(self):
        self.objects = {}
        self.writes = []

    def exists(self, key):
        return key in self.objects

    def read_bytes(self, key, *, max_bytes=5_000_000):
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]

    def write_bytes_atomic(self, key, payload):
        self.objects[key] = bytes(payload)
        self.writes.append(key)
        return None


def _resolver_module():
    name = "sports_api.wnba_roster_identity_resolver_v1"
    assert importlib.util.find_spec(name) is not None, "resilient WNBA roster identity resolver is not implemented yet"
    import sports_api.wnba_roster_identity_resolver_v1 as module

    return module


def _official(players=None):
    rows = OFFICIAL_PLAYERS if players is None else players
    return {
        "source": "WNBA Stats API",
        "season": 2026,
        "current_roster_only": True,
        "retrieved_at_utc": NOW.isoformat(),
        "players": [dict(row) for row in rows],
    }


def _primary_success(season, *, current_roster_only=True):
    assert season == 2026
    assert current_roster_only is True
    return _official()


def _primary_timeout(season, *, current_roster_only=True):
    raise WNBAStatsUpstreamError("official roster timeout")


def _espn_exact(team_key, season):
    assert season == 2026
    names = {
        "dream": ["Allisha Gray", "Rhyne Howard"],
        "valkyries": ["Veronica Burton"],
    }
    return [{"full_name": name, "team_key": team_key, "espn_player_id": f"espn-{i}"} for i, name in enumerate(names[team_key], 1)]


def _write_cache(storage, module, players, stored_at):
    payload = {
        "schema_version": 1,
        "season": 2026,
        "stored_at_utc": stored_at.isoformat(),
        "source": "WNBA Stats API",
        "players": players,
    }
    storage.objects[module.ROSTER_CACHE_KEY] = json.dumps(payload, sort_keys=True).encode("utf-8")


def test_primary_official_roster_success_writes_durable_canonical_cache():
    module = _resolver_module()
    storage = MemoryStorage()

    result = module.resolve_verified_roster(
        2026,
        PLAYABLE_GAMES,
        primary_getter=_primary_success,
        storage=storage,
        espn_roster_getter=_espn_exact,
        now_utc=NOW,
    )

    assert result["resolution"]["mode"] == "OFFICIAL_PRIMARY"
    assert {row["player_id"] for row in result["players"]} == {101, 102, 201}
    assert storage.writes == [module.ROSTER_CACHE_KEY]
    cached = json.loads(storage.objects[module.ROSTER_CACHE_KEY])
    assert {row["player_id"] for row in cached["players"]} == {101, 102, 201}


def test_primary_timeout_uses_fresh_official_cache_only_after_exact_espn_corroboration():
    module = _resolver_module()
    storage = MemoryStorage()
    _write_cache(storage, module, OFFICIAL_PLAYERS, NOW - timedelta(minutes=5))

    result = module.resolve_verified_roster(
        2026,
        PLAYABLE_GAMES,
        primary_getter=_primary_timeout,
        storage=storage,
        espn_roster_getter=_espn_exact,
        now_utc=NOW,
    )

    assert result["resolution"]["mode"] == "DURABLE_OFFICIAL_PLUS_ESPN_CORROBORATION"
    by_name = {row["full_name"]: row for row in result["players"]}
    assert by_name["Allisha Gray"]["player_id"] == 101
    assert by_name["Veronica Burton"]["player_id"] == 201
    assert all(row["identity_source"] == "DURABLE_OFFICIAL_ID+ESPN_CURRENT_MEMBERSHIP" for row in result["players"])


def test_primary_timeout_espn_disagreement_removes_only_disputed_player():
    module = _resolver_module()
    storage = MemoryStorage()
    _write_cache(storage, module, OFFICIAL_PLAYERS, NOW - timedelta(minutes=5))

    def espn(team_key, season):
        rows = _espn_exact(team_key, season)
        return [row for row in rows if row["full_name"] != "Rhyne Howard"]

    result = module.resolve_verified_roster(
        2026,
        PLAYABLE_GAMES,
        primary_getter=_primary_timeout,
        storage=storage,
        espn_roster_getter=espn,
        now_utc=NOW,
    )

    assert {row["full_name"] for row in result["players"]} == {"Allisha Gray", "Veronica Burton"}
    assert result["resolution"]["rejected_player_count"] == 1


def test_ambiguous_same_name_team_identity_fails_player_closed():
    module = _resolver_module()
    storage = MemoryStorage()
    ambiguous = [
        {**OFFICIAL_PLAYERS[0], "player_id": 101},
        {**OFFICIAL_PLAYERS[0], "player_id": 999},
        OFFICIAL_PLAYERS[2],
    ]
    _write_cache(storage, module, ambiguous, NOW - timedelta(minutes=5))

    result = module.resolve_verified_roster(
        2026,
        PLAYABLE_GAMES,
        primary_getter=_primary_timeout,
        storage=storage,
        espn_roster_getter=_espn_exact,
        now_utc=NOW,
    )

    assert "Allisha Gray" not in {row["full_name"] for row in result["players"]}
    assert {row["player_id"] for row in result["players"]} == {201}


def test_stale_durable_canonical_cache_is_rejected():
    module = _resolver_module()
    storage = MemoryStorage()
    _write_cache(storage, module, OFFICIAL_PLAYERS, NOW - timedelta(seconds=module.ROSTER_CACHE_TTL_SECONDS + 1))

    with pytest.raises(module.WNBARosterIdentityNotReadyError, match="stale"):
        module.resolve_verified_roster(
            2026,
            PLAYABLE_GAMES,
            primary_getter=_primary_timeout,
            storage=storage,
            espn_roster_getter=_espn_exact,
            now_utc=NOW,
        )


def test_missing_durable_cache_after_primary_timeout_fails_closed():
    module = _resolver_module()
    storage = MemoryStorage()

    with pytest.raises(module.WNBARosterIdentityNotReadyError, match="cache"):
        module.resolve_verified_roster(
            2026,
            PLAYABLE_GAMES,
            primary_getter=_primary_timeout,
            storage=storage,
            espn_roster_getter=_espn_exact,
            now_utc=NOW,
        )


def test_prop_line_adapter_exposes_injectable_roster_resolver_boundary():
    params = inspect.signature(build_prop_line_feed_board).parameters
    assert "roster_resolver" in params
