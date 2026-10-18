from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from sports_api.collectors.wnba_fanduel_direct import FANDUEL_PROVIDER_ID
from sports_api.wnba_roster_identity_resolver_v1 import resolve_verified_roster
from sports_api.wnba_rosters import WNBAStatsUpstreamError


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 18, 19, 15, tzinfo=timezone.utc)
PLAYABLE = [
    {
        "game_id": "401999001",
        "away": {"team_key": "dream", "full_name": "Atlanta Dream"},
        "home": {"team_key": "valkyries", "full_name": "Golden State Valkyries"},
        "verification": {"playable_pregame": True},
    }
]
OFFICIAL = [
    {"player_id": 101, "full_name": "Allisha Gray", "display_last_comma_first": "Gray, Allisha", "team_key": "dream"},
    {"player_id": 201, "full_name": "Veronica Burton", "display_last_comma_first": "Burton, Veronica", "team_key": "valkyries"},
]


class MemoryStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def read_bytes(self, key, *, max_bytes=5_000_000):
        del max_bytes
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]

    def write_bytes_atomic(self, key, payload):
        self.objects[key] = bytes(payload)
        return None


def _official_success(season, *, current_roster_only=True):
    assert season == 2026 and current_roster_only is True
    return {
        "source": "WNBA Stats API",
        "season": 2026,
        "current_roster_only": True,
        "retrieved_at_utc": NOW.isoformat(),
        "players": [dict(row) for row in OFFICIAL],
    }


def _official_timeout(season, *, current_roster_only=True):
    del season, current_roster_only
    raise WNBAStatsUpstreamError("official roster timeout")


def _espn_exact(team_key, season):
    assert season == 2026
    names = {"dream": ["Allisha Gray"], "valkyries": ["Veronica Burton"]}
    return [{"full_name": name, "team_key": team_key} for name in names[team_key]]


def test_exact_official_identity_is_cached_then_reused_only_with_live_corroboration():
    from sports_api.wnba_roster_identity_resolver_v1 import ROSTER_CACHE_KEY

    storage = MemoryStorage()
    primary = resolve_verified_roster(
        2026,
        PLAYABLE,
        primary_getter=_official_success,
        storage=storage,
        espn_roster_getter=_espn_exact,
        now_utc=NOW,
    )
    assert primary["resolution"]["mode"] == "OFFICIAL_PRIMARY"
    assert ROSTER_CACHE_KEY in storage.objects

    cached = json.loads(storage.objects[ROSTER_CACHE_KEY].decode("utf-8"))
    cached["stored_at_utc"] = (NOW - timedelta(minutes=5)).isoformat()
    storage.objects[ROSTER_CACHE_KEY] = json.dumps(cached, sort_keys=True).encode("utf-8")

    fallback = resolve_verified_roster(
        2026,
        PLAYABLE,
        primary_getter=_official_timeout,
        storage=storage,
        espn_roster_getter=_espn_exact,
        now_utc=NOW,
    )
    assert fallback["resolution"]["mode"] == "DURABLE_OFFICIAL_PLUS_ESPN_CORROBORATION"
    assert {(row["full_name"], row["player_id"]) for row in fallback["players"]} == {
        ("Allisha Gray", 101),
        ("Veronica Burton", 201),
    }
    assert all(row["identity_source"] == "DURABLE_OFFICIAL_ID+ESPN_CURRENT_MEMBERSHIP" for row in fallback["players"])


def test_step5m_successor_preserves_v1_normalizer_and_routes_through_resilient_identity():
    source = (ROOT / "sports_api/wnba_prop_line_feed_adapter.py").read_text(encoding="utf-8")
    assert "import sports_api.wnba_prop_line_feed_adapter_v1 as previous" in source
    assert "roster_resolver: Callable[..., dict[str, Any]] = resolve_verified_roster" in source
    assert "roster = roster_resolver(" in source
    assert "return previous.build_prop_line_feed_board(" in source
    assert "line_board_builder=build_prop_line_feed_board" in source


def test_fanduel_is_first_class_provider_without_replacing_sequential_v1_failover():
    source = (ROOT / "sports_api/wnba_prop_feed_failover.py").read_text(encoding="utf-8")
    assert FANDUEL_PROVIDER_ID == "fanduel"
    assert "if provider_id == FANDUEL_PROVIDER_ID:" in source
    assert "fanduel_collector: Callable[..., dict[str, Any]] = collect_fanduel_wnba_feed" in source
    assert "return previous.collect_failover_line_board(" in source
    assert "generic_collector=bridged_generic_collector" in source
    assert '"projection_influence": 0.0' in source


def test_streamlit_market_bridge_remains_api_owned_and_freshness_gated():
    source = (ROOT / "wnba_pra_api_market_bridge_v1.py").read_text(encoding="utf-8")
    assert 'SNAPSHOT_PATH = "/api/v1/wnba/markets/player-props/collection-store/snapshots"' in source
    assert "SNAPSHOT_MAX_AGE_SECONDS = 600.0" in source
    assert 'state = "STALE_STORED_MARKETS"' in source
    assert "KyreWNBAAPIClient()" in source
    assert "api.sportsbook.fanduel.com" not in source
