from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_SPEED_MODULES = [
    "wnba_pra_source_clean_guard_v1.py",
    "wnba_pra_page_model_artifact_v1.py",
    "wnba_pra_page_snapshot_publish_v1.py",
    "runless_v2/wnba_pra_page_snapshot_store_v1.py",
    "runless_v2/wnba_pra_page_snapshot_v1.py",
    "wnba_pra_page_snapshot_client_v1.py",
    "wnba_pra_page_snapshot_renderer_v1.py",
]
FORBIDDEN = ("sportsgameodds", "sgo", "espn", "espn bet", "onrender")


def _artifact(line: float = 23.5) -> dict:
    return {
        "schema_version": "wnba_pra_page_model_artifact_v1",
        "date": "2026-10-21",
        "season": 2026,
        "generated_at": "2026-10-21T18:00:00+00:00",
        "model_version": "PRA V3.6.17",
        "rows": [
            {
                "source_event_id": "evt-gsv-atl",
                "player_name": "Rhyne Howard",
                "team": "Atlanta Dream",
                "opponent": "Golden State Valkyries",
                "line": line,
                "p_over": 0.581,
                "p_under": 0.419,
                "fair_over": -139,
                "fair_under": 139,
                "edge": 0.041,
                "ev100": 8.2,
                "final_ready": True,
                "projection_pra": 25.2,
                "context_quality": 0.87,
            }
        ],
        "final_card": [
            {
                "source_event_id": "evt-gsv-atl",
                "player_name": "Rhyne Howard",
                "line": line,
                "side": "over",
                "final_ready": True,
            }
        ],
        "diagnostics": {"source_clean": True},
    }


def _market_board(line: float = 23.5) -> dict:
    return {
        "service": "Kyre Sports API — Vercel",
        "state": "READY",
        "date": "2026-10-21",
        "season": 2026,
        "selected_provider": "draftkings",
        "sportsbooks": ["DraftKings"],
        "consensus_averaging": False,
        "projection_weight": 0.0,
        "offers": [
            {
                "sportsbook": "DraftKings",
                "provider_id": "draftkings",
                "source_event_id": "evt-gsv-atl",
                "player_name": "Rhyne Howard",
                "stat": "pra",
                "side": "over",
                "line": line,
                "american_odds": -119,
                "market_captured_at_utc": "2026-10-21T18:04:50+00:00",
                "source_market_id": "mkt-1",
                "source_outcome_id": "out-1",
            },
            {
                "sportsbook": "DraftKings",
                "provider_id": "draftkings",
                "source_event_id": "evt-gsv-atl",
                "player_name": "Rhyne Howard",
                "stat": "pra",
                "side": "under",
                "line": line,
                "american_odds": -114,
                "market_captured_at_utc": "2026-10-21T18:04:50+00:00",
                "source_market_id": "mkt-1",
                "source_outcome_id": "out-2",
            },
        ],
        "provider_health": [
            {"provider_id": "fanduel", "state": "EMPTY", "pra_offer_count": 0, "error": None},
            {"provider_id": "draftkings", "state": "READY", "pra_offer_count": 2, "error": None},
        ],
    }


class FakeStore:
    def __init__(self, artifact: dict):
        self.artifact = deepcopy(artifact)
        self.reads = 0

    def read(self, *, date: str, season: int, schema_version: str):
        self.reads += 1
        assert date == "2026-10-21"
        assert season == 2026
        assert schema_version == "wnba_pra_page_model_artifact_v1"
        return deepcopy(self.artifact)


def test_active_speed_modules_are_source_clean():
    missing = [rel for rel in ACTIVE_SPEED_MODULES if not (ROOT / rel).exists()]
    assert not missing, f"missing active speed modules: {missing}"
    for rel in ACTIVE_SPEED_MODULES:
        source = (ROOT / rel).read_text(encoding="utf-8").casefold()
        for token in FORBIDDEN:
            assert token not in source, f"{rel} contains forbidden active-source token {token!r}"


def test_page_snapshot_reads_market_once_and_preserves_exact_quote_fields():
    from runless_v2.wnba_pra_page_snapshot_v1 import build_page_snapshot

    calls = []
    board = _market_board()

    def market_builder(*, date: str, season: int):
        calls.append((date, season))
        return deepcopy(board)

    store = FakeStore(_artifact())
    out = build_page_snapshot(
        date="2026-10-21",
        season=2026,
        store=store,
        market_board_builder=market_builder,
        now_utc=datetime(2026, 10, 21, 18, 5, tzinfo=timezone.utc),
    )

    assert calls == [("2026-10-21", 2026)]
    assert store.reads == 1
    assert out["market_board_reads"] == 1
    assert out["consensus_averaging"] is False
    assert out["snapshot_state"] == "READY"
    assert len(out["offers"]) == 2
    for original, merged in zip(board["offers"], out["offers"], strict=True):
        for field in (
            "sportsbook",
            "provider_id",
            "source_event_id",
            "source_market_id",
            "source_outcome_id",
            "player_name",
            "side",
            "line",
            "american_odds",
            "market_captured_at_utc",
        ):
            assert merged[field] == original[field]
    assert out["offers"][0]["model_state"] == "LINE_BOUND_READY"
    assert out["offers"][0]["p_over"] == pytest.approx(0.581)
    assert out["final_card"][0]["line"] == 23.5


def test_moved_line_is_refresh_required_and_never_inherits_old_probability():
    from runless_v2.wnba_pra_page_snapshot_v1 import build_page_snapshot

    store = FakeStore(_artifact(line=23.5))
    out = build_page_snapshot(
        date="2026-10-21",
        season=2026,
        store=store,
        market_board_builder=lambda **_: _market_board(line=24.5),
        now_utc=datetime(2026, 10, 21, 18, 5, tzinfo=timezone.utc),
    )

    assert out["snapshot_state"] == "MODEL_REFRESH_REQUIRED"
    assert out["refresh_required"] is True
    assert out["final_card"] == []
    for offer in out["offers"]:
        assert offer["line"] == 24.5
        assert offer["model_state"] == "MODEL_REFRESH_REQUIRED"
        for forbidden_model_field in ("p_over", "p_under", "fair_over", "fair_under", "edge", "ev100", "final_ready"):
            assert forbidden_model_field not in offer


def test_source_clean_generation_neutralizes_legacy_history_network_fallbacks(monkeypatch):
    import sys
    import types

    from wnba_pra_source_clean_guard_v1 import source_clean_generation

    fake = types.ModuleType("wnba_players_v25")
    calls = []

    def network_fallback(*args, **kwargs):
        calls.append((args, kwargs))
        return "NETWORK"

    fake._espn_roster = network_fallback
    fake._espn_season_schedule = network_fallback
    fake._espn_game_summary = network_fallback
    monkeypatch.setitem(sys.modules, "wnba_players_v25", fake)

    with source_clean_generation() as guard:
        assert getattr(fake._espn_roster(1), "empty", False) is True
        assert getattr(fake._espn_season_schedule(2026), "empty", False) is True
        assert getattr(fake._espn_game_summary("g1"), "empty", False) is True
        assert guard.blocked_calls == 3
        assert calls == []

    assert fake._espn_roster(1) == "NETWORK"
    assert len(calls) == 1


def test_model_artifact_is_line_bound_hash_validated_and_quote_free():
    from wnba_pra_page_model_artifact_v1 import build_model_artifact, validate_model_artifact

    fixture = {
        "schedule": [{"game_id": "g1", "away_team": "Golden State Valkyries", "home_team": "Atlanta Dream"}],
        "projections": [
            {
                "game_id": "g1",
                "player_key": "p1",
                "PLAYER_NAME": "Rhyne Howard",
                "TEAM_NAME": "Atlanta Dream",
                "OPPONENT": "Golden State Valkyries",
                "PROJ_PRA": 25.2,
                "PROJ_MIN": 34.0,
            }
        ],
        "stored_mc_rows": [
            {
                "game_id": "g1",
                "player_key": "p1",
                "player": "Rhyne Howard",
                "team": "Atlanta Dream",
                "opponent": "Golden State Valkyries",
                "line": 23.5,
                "book": "DraftKings",
                "over_odds": -119,
                "under_odds": -114,
                "model_over": 0.581,
                "no_vig_over": 0.54,
                "edge": 0.041,
                "ev100": 8.2,
                "final_ready": True,
                "converged": True,
                "data_quality": 0.92,
                "context_quality": 0.87,
                "variance_source": "EMPIRICAL CORRELATED",
                "pass_source": "5M",
            }
        ],
        "final_card": [
            {
                "game_id": "g1",
                "player_key": "p1",
                "player": "Rhyne Howard",
                "line": 23.5,
                "side": "over",
                "final_ready": True,
                "decision_label": "BEST BET",
            }
        ],
        "schedule_diag": {"ok": True},
        "market_meta": {"source": "Kyre Sports API"},
        "matchup_meta": {"quality": 0.87},
        "stored_mc_meta": {"source": "5M"},
        "availability_diag": {},
        "role_diag": {},
    }

    artifact = build_model_artifact(
        "2026-10-21",
        season=2026,
        snapshot_builder=lambda day: fixture,
        now_utc=datetime(2026, 10, 21, 18, 0, tzinfo=timezone.utc),
    )
    validated = validate_model_artifact(artifact)

    assert validated["schema_version"] == "wnba_pra_page_model_artifact_v1"
    assert validated["date"] == "2026-10-21"
    assert validated["content_hash"].startswith("sha256:")
    assert len(validated["rows"]) == 1
    row = validated["rows"][0]
    assert row["line"] == 23.5
    assert row["p_over"] == pytest.approx(0.581)
    assert row["p_under"] == pytest.approx(0.419)
    assert row["model_pass"] == "5M"
    assert "book" not in row
    assert "over_odds" not in row
    assert "under_odds" not in row
    assert validated["line_bindings"]["rhynehoward|23.500"]["line"] == 23.5

    tampered = deepcopy(validated)
    tampered["rows"][0]["p_over"] = 0.9
    with pytest.raises(ValueError, match="content hash"):
        validate_model_artifact(tampered)


def test_snapshot_store_reads_one_private_artifact_and_atomic_refresh_claim():
    from runless_v2.wnba_pra_page_snapshot_store_v1 import WNBAPRASnapshotStore

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)
        def json(self):
            return deepcopy(self._payload)

    class Client:
        def __init__(self):
            self.calls = []
        def get(self, url, *, headers, params):
            self.calls.append(("GET", url, deepcopy(headers), deepcopy(params)))
            return Response(200, [{"artifact": _artifact(), "content_hash": "hash", "generated_at": "2026-10-21T18:00:00+00:00"}])
        def post(self, url, *, headers, json):
            self.calls.append(("POST", url, deepcopy(headers), deepcopy(json)))
            if url.endswith("/rpc/claim_wnba_pra_snapshot_refresh"):
                return Response(200, [{"acquired": True, "lease_token": "lease-1", "expires_at": "2026-10-21T18:10:00+00:00"}])
            raise AssertionError(url)

    client = Client()
    settings = type("S", (), {"supabase_url": "https://project.supabase.co", "supabase_service_role_key": "sb_secret_test"})()
    store = WNBAPRASnapshotStore(settings, client=client)

    got = store.read(date="2026-10-21", season=2026, schema_version="wnba_pra_page_model_artifact_v1")
    claim = store.claim_refresh(date="2026-10-21", season=2026, owner_id="streamlit-a", ttl_seconds=120)

    assert got["date"] == "2026-10-21"
    assert claim["acquired"] is True
    assert claim["lease_token"] == "lease-1"
    assert client.calls[0][2]["Accept-Profile"] == "runless_v2"
    assert client.calls[1][2]["Content-Profile"] == "runless_v2"
    assert "Authorization" not in client.calls[0][2]
    assert client.calls[0][2]["apikey"] == "sb_secret_test"


def test_two_store_instances_can_only_observe_one_refresh_winner():
    from runless_v2.wnba_pra_page_snapshot_store_v1 import WNBAPRASnapshotStore

    class Response:
        status_code = 200
        text = "ok"
        def __init__(self, acquired): self.acquired = acquired
        def json(self):
            return [{"acquired": self.acquired, "lease_token": "lease-1" if self.acquired else None, "expires_at": "2026-10-21T18:10:00+00:00"}]

    class SharedClient:
        def __init__(self): self.claims = 0
        def post(self, url, *, headers, json):
            assert url.endswith("/rpc/claim_wnba_pra_snapshot_refresh")
            self.claims += 1
            return Response(self.claims == 1)

    shared = SharedClient()
    settings = type("S", (), {"supabase_url": "https://project.supabase.co", "supabase_service_role_key": "sb_secret_test"})()
    a = WNBAPRASnapshotStore(settings, client=shared)
    b = WNBAPRASnapshotStore(settings, client=shared)
    one = a.claim_refresh(date="2026-10-21", season=2026, owner_id="a", ttl_seconds=120)
    two = b.claim_refresh(date="2026-10-21", season=2026, owner_id="b", ttl_seconds=120)
    assert [one["acquired"], two["acquired"]] == [True, False]


def test_page_snapshot_fresh_exact_line_overlay_and_model_ttl_states():
    from runless_v2.wnba_pra_page_snapshot_v1 import build_page_snapshot

    for age_seconds, expected_cache in [(299, "FRESH"), (301, "STALE_SAFE"), (901, "MODEL_UNAVAILABLE")]:
        generated = datetime(2026, 10, 21, 18, 5, tzinfo=timezone.utc).timestamp() - age_seconds
        artifact = _artifact()
        artifact["generated_at"] = datetime.fromtimestamp(generated, timezone.utc).isoformat()
        store = FakeStore(artifact)
        out = build_page_snapshot(
            date="2026-10-21",
            season=2026,
            store=store,
            market_board_builder=lambda **_: _market_board(),
            now_utc=datetime(2026, 10, 21, 18, 5, tzinfo=timezone.utc),
        )
        assert out["cache_state"] == expected_cache
        assert out["market_board_reads"] == 1
        assert out["consensus_averaging"] is False
        if expected_cache == "MODEL_UNAVAILABLE":
            assert out["snapshot_state"] == "MODEL_UNAVAILABLE"
            assert all("p_over" not in offer for offer in out["offers"])
        else:
            assert out["offers"][0]["p_over"] == pytest.approx(0.581)


def test_snapshot_router_requires_constant_time_bearer_for_publish_and_refresh_claim(monkeypatch):
    import runless_v2.wnba_pra_page_snapshot_v1 as route

    monkeypatch.setenv("WNBA_PRA_SNAPSHOT_PUBLISH_TOKEN", "secret-token")
    with pytest.raises(Exception) as no_auth:
        route.require_publish_token(None)
    assert getattr(no_auth.value, "status_code", None) == 401
    with pytest.raises(Exception) as bad_auth:
        route.require_publish_token("Bearer wrong")
    assert getattr(bad_auth.value, "status_code", None) == 401
    route.require_publish_token("Bearer secret-token")


def test_private_snapshot_migration_defines_atomic_lease_and_no_public_grants():
    migration = ROOT / "supabase/migrations/20261021_wnba_pra_page_snapshots_v1.sql"
    assert migration.exists()
    source = migration.read_text(encoding="utf-8").casefold()
    assert "create table if not exists runless_v2.wnba_pra_page_snapshots" in source
    assert "create table if not exists runless_v2.wnba_pra_snapshot_refresh_leases" in source
    assert "claim_wnba_pra_snapshot_refresh" in source
    assert "release_wnba_pra_snapshot_refresh" in source
    assert "on conflict (snapshot_date, season) do update" in source
    assert "where runless_v2.wnba_pra_snapshot_refresh_leases.expires_at <=" in source
    assert "revoke all on table runless_v2.wnba_pra_page_snapshots from public, anon, authenticated" in source
    assert "revoke all on table runless_v2.wnba_pra_snapshot_refresh_leases from public, anon, authenticated" in source
    assert "security definer" not in source


def test_runless_app_mounts_snapshot_router_in_primary_and_fallback_apps():
    source = (ROOT / "runless_v2/app.py").read_text(encoding="utf-8")
    assert "from .wnba_pra_page_snapshot_v1 import router as wnba_pra_page_snapshot_router" in source
    assert source.count("include_router(wnba_pra_page_snapshot_router)") == 2


def test_publish_uses_atomic_refresh_fence_rpc():
    from runless_v2.wnba_pra_page_snapshot_store_v1 import WNBAPRASnapshotStore

    class Response:
        status_code = 200
        text = "ok"
        def json(self): return [{"stored": True, "content_hash": "sha256:" + "a" * 64}]
    class Client:
        def __init__(self): self.call = None
        def post(self, url, *, headers, json):
            self.call = (url, deepcopy(headers), deepcopy(json))
            return Response()
    client = Client()
    settings = type("S", (), {"supabase_url": "https://project.supabase.co", "supabase_service_role_key": "sb_secret_test"})()
    store = WNBAPRASnapshotStore(settings, client=client)
    artifact = _artifact()
    artifact.update({"content_hash": "sha256:" + "a" * 64, "model_version": "PRA V3.6.17"})
    result = store.publish_with_lease(artifact, owner_id="worker-a", lease_token="lease-a")
    assert result["stored"] is True
    assert client.call[0].endswith("/rpc/publish_wnba_pra_page_snapshot")
    assert client.call[2]["p_owner_id"] == "worker-a"
    assert client.call[2]["p_lease_token"] == "lease-a"


def test_publish_fence_migration_rejects_wrong_or_expired_lease():
    migration = ROOT / "supabase/migrations/20261021_wnba_pra_page_snapshot_publish_fence_v1.sql"
    assert migration.exists()
    source = migration.read_text(encoding="utf-8").casefold()
    assert "publish_wnba_pra_page_snapshot" in source
    assert "lease_token = p_lease_token" in source
    assert "owner_id = btrim(p_owner_id)" in source
    assert "expires_at > clock_timestamp()" in source
    assert "wnba_pra_snapshot_publish_fence_invalid" in source
    assert "security definer" not in source


def test_task5_exact_line_equivalence_preserves_preserved_mc_fields_and_quote_ids():
    from types import SimpleNamespace
    import pandas as pd
    from wnba_pra_page_model_artifact_v1 import build_model_artifact
    from runless_v2.wnba_pra_page_snapshot_v1 import build_page_snapshot

    preserved = {
        "game_id": "g1", "player_key": "p1", "player": "Rhyne Howard",
        "team": "Atlanta Dream", "opponent": "Golden State Valkyries", "line": 23.5,
        "model_over": .641, "no_vig_over": .523, "edge": .118, "ev100": 12.4,
        "final_ready": True, "model_qualified": True, "converged": True,
        "data_quality": .96, "context_quality": .91, "variance_source": "EMPIRICAL",
        "pass_source": "10M", "projection": 25.2,
    }
    snapshot = SimpleNamespace(
        schedule=pd.DataFrame([{"game_id":"g1","away_team":"Golden State Valkyries","home_team":"Atlanta Dream"}]),
        projections=pd.DataFrame([{"game_id":"g1","player_key":"p1","PLAYER_NAME":"Rhyne Howard","TEAM_NAME":"Atlanta Dream","OPPONENT":"Golden State Valkyries","PROJ_PRA":25.2,"PROJ_MIN":34.0}]),
        stored_mc_rows=pd.DataFrame([preserved]),
        final_card=pd.DataFrame([{**preserved, "decision_label":"🔥 BEST BET"}]),
        schedule_diag={}, market_meta={}, matchup_meta={}, stored_mc_meta={"source":"5M/10M"}, availability_diag={}, role_diag={},
    )
    artifact = build_model_artifact("2026-10-21", snapshot_builder=lambda _day: snapshot,
        now_utc=datetime.fromisoformat("2026-10-21T18:00:00+00:00"))

    class Store:
        def read(self, **_kwargs): return deepcopy(artifact)

    board = _market_board(23.5)
    for row in board["offers"]:
        row["market_id"] = "pra-main"
        row["outcome_id"] = "rhyne-over" if row["side"] == "over" else "rhyne-under"
    out = build_page_snapshot(
        date="2026-10-21", season=2026, store=Store(), market_board_builder=lambda **_kwargs: deepcopy(board),
        now_utc=datetime.fromisoformat("2026-10-21T18:02:00+00:00"),
    )
    assert out["snapshot_state"] == "READY"
    over = next(x for x in out["offers"] if x["side"] == "over")
    assert over["sportsbook"] == "DraftKings"
    assert over["line"] == pytest.approx(23.5)
    assert over["american_odds"] == -119
    assert over["market_id"] == "pra-main"
    assert over["outcome_id"] == "rhyne-over"
    assert over["p_over"] == pytest.approx(preserved["model_over"])
    assert over["no_vig_over"] == pytest.approx(preserved["no_vig_over"])
    assert over["edge"] == pytest.approx(preserved["edge"])
    assert over["ev100"] == pytest.approx(preserved["ev100"])
    assert over["final_ready"] is True
    assert over["projection_pra"] == pytest.approx(preserved["projection"])
    assert out["consensus_averaging"] is False


def test_task5_degraded_provider_and_malformed_artifact_fail_safe_without_fake_model_math():
    from runless_v2.wnba_pra_page_snapshot_v1 import build_page_snapshot

    class Store:
        def read(self, **_kwargs):
            return {"date":"2026-10-21","season":2026,"generated_at":"not-a-time","rows":"bad","final_card":"bad"}

    board = _market_board(23.5)
    board["provider_health"] = [{"provider_id":"fanduel","state":"DEGRADED"},{"provider_id":"draftkings","state":"READY"}]
    with pytest.raises((ValueError, TypeError)):
        build_page_snapshot(date="2026-10-21", season=2026, store=Store(), market_board_builder=lambda **_kwargs: deepcopy(board))


def test_task5_initial_hub_does_not_import_or_call_speed_v3_player_detail_endpoint():
    source = (ROOT / "wnba_pra_hub_v3617.py").read_text(encoding="utf-8").casefold()
    assert "pra-detail-cached" not in source
    assert "wnba_pra_speed_v3_step7_precompute" not in source
    assert "wnba_pra_speed_v3_step4_cache" not in source
    assert "wnba_pra_game_center_v2_step3" not in source


def test_task5_profiler_emits_required_fields_and_enforces_targets():
    from devsystem.wnba_pra_max_speed_profile_v1 import profile_snapshot, evaluate_profile

    ticks = iter([0.000, 0.080, 0.090, 0.100])
    payload = _market_board(23.5)
    payload.update({
        "schema_version":"wnba_pra_page_snapshot_v1", "snapshot_state":"READY", "cache_state":"FRESH",
        "assembly_ms":31.0, "market_board_reads":1, "refresh_required":False,
    })
    calls = {"fetch":0,"render":0}
    def fetch(): calls["fetch"] += 1; return deepcopy(payload)
    def render(body): calls["render"] += 1; assert body["snapshot_state"] == "READY"
    result = profile_snapshot(
        candidate_sha="a"*40, load_class="warm", fetch=fetch, render=render,
        perf_counter=lambda: next(ticks), duplicate_refresh_count=0,
    )
    assert result["candidate_sha"] == "a"*40
    assert result["schema"] == "wnba_pra_page_snapshot_v1"
    assert result["cache_state"] == "FRESH"
    assert result["initial_network_reads"] == 1
    assert result["market_board_reads"] == 1
    assert result["duplicate_refresh_count"] == 0
    assert result["backend_ms"] == pytest.approx(31.0)
    assert result["client_ms"] == pytest.approx(80.0)
    assert result["render_ms"] == pytest.approx(10.0)
    assert result["total_ms"] == pytest.approx(100.0)
    verdict = evaluate_profile(result)
    assert verdict["passed"] is True
    assert verdict["failures"] == []
    assert calls == {"fetch":1,"render":1}


def test_task5_profiler_fails_closed_on_latency_or_duplicate_refresh():
    from devsystem.wnba_pra_max_speed_profile_v1 import evaluate_profile
    bad = {
        "load_class":"normal_fresh", "total_ms":1001.0, "initial_network_reads":2,
        "market_board_reads":2, "duplicate_refresh_count":1,
    }
    verdict = evaluate_profile(bad)
    assert verdict["passed"] is False
    assert {x["code"] for x in verdict["failures"]} == {
        "TOTAL_LATENCY_TARGET_MISSED", "INITIAL_NETWORK_READS_NOT_ONE",
        "MARKET_BOARD_READS_NOT_ONE", "DUPLICATE_REFRESH_DETECTED",
    }


def test_reference_fallback_parses_current_roster_season_stats_and_combined_logs():
    from wnba_pra_source_clean_guard_v1 import _ReferenceFallback, _stable_player_id

    season_html = """
    <table><tbody>
    <tr><th data-stat='player'><a href='/wnba/players/h/howarrh01w.html'>Rhyne Howard</a></th><td data-stat='team'>ATL</td><td data-stat='pos'>G</td><td data-stat='g'>43</td><td data-stat='mp_per_g'>34.2</td><td data-stat='pts_per_g'>17.7</td><td data-stat='trb_per_g'>3.8</td><td data-stat='ast_per_g'>3.7</td></tr>
    <tr><th data-stat='player'><a href='/wnba/players/b/benchxx01w.html'>Bench Player</a></th><td data-stat='team'>ATL</td><td data-stat='pos'>F</td><td data-stat='g'>30</td><td data-stat='mp_per_g'>12.0</td><td data-stat='pts_per_g'>4.0</td><td data-stat='trb_per_g'>2.0</td><td data-stat='ast_per_g'>1.0</td></tr>
    </tbody></table>"""
    team_html = """
    <table><tbody>
    <tr><th data-stat='player'><a href='/wnba/players/h/howarrh01w.html'>Rhyne Howard</a></th><td data-stat='pos'>G</td></tr>
    <tr><th data-stat='player'><a href='/wnba/players/b/benchxx01w.html'>Bench Player</a></th><td data-stat='pos'>F</td></tr>
    </tbody></table>"""
    regular_html = """
    <table><tbody>
    <tr><th data-stat='date_game'>Date</th><td data-stat='team_id'>Tm</td><td data-stat='opp_id'>Opp</td><td data-stat='mp'>MP</td><td data-stat='pts'>PTS</td><td data-stat='trb'>TRB</td><td data-stat='ast'>AST</td></tr>
    <tr><th data-stat='date_game'>2026-09-23</th><td data-stat='team_id'>ATL</td><td data-stat='opp_id'>NYL</td><td data-stat='mp'>34:08</td><td data-stat='pts'>8</td><td data-stat='trb'>4</td><td data-stat='ast'>6</td></tr>
    </tbody></table>"""
    playoffs_html = """
    <table><tbody>
    <tr><th data-stat='date_game'>2026-10-17</th><td data-stat='team_id'>ATL</td><td data-stat='opp_id'>GSV</td><td data-stat='mp'>38:00</td><td data-stat='pts'>12</td><td data-stat='trb'>7</td><td data-stat='ast'>4</td></tr>
    <tr><th data-stat='date_game'>2026-10-19</th><td data-stat='team_id'>ATL</td><td data-stat='opp_id'>GSV</td><td data-stat='mp'>27:00</td><td data-stat='pts'>5</td><td data-stat='trb'>2</td><td data-stat='ast'>2</td></tr>
    <tr><th data-stat='date_game'>2026-10-21</th><td data-stat='team_id'>ATL</td><td data-stat='opp_id'>GSV</td><td data-stat='mp'>0:00</td><td data-stat='pts'>0</td><td data-stat='trb'>0</td><td data-stat='ast'>0</td></tr>
    </tbody></table>"""

    class Response:
        status_code = 200
        def __init__(self, text): self.text = text
    class Session:
        def __init__(self): self.urls=[]
        def get(self, url, *, headers, timeout):
            self.urls.append(url)
            if url.endswith('/wnba/years/2026_per_game.html'): return Response(season_html)
            if url.endswith('/wnba/teams/ATL/2026.html'): return Response(team_html)
            if url.endswith('/wnba/teams/GSV/2026.html'): return Response('<table></table>')
            if url.endswith('/wnba/players/h/howarrh01w/gamelog/2026/'): return Response(regular_html)
            if url.endswith('/wnba/players/h/howarrh01w/gamelog-playoffs/'): return Response(playoffs_html)
            if 'benchxx01w' in url: return Response('<table></table>')
            raise AssertionError(url)

    schedule = {"games":[{"away":{"official_team_id":1611661331,"full_name":"Golden State Valkyries","team_tricode":"GSV"},"home":{"official_team_id":1611661330,"full_name":"Atlanta Dream","team_tricode":"ATL"}}]}
    fallback = _ReferenceFallback('2026-10-21', 2026, session=Session(), schedule_payload=schedule, focus_names={'Rhyne Howard'})
    roster = fallback.roster(1611661330, 'Atlanta Dream', 'ATL')
    assert roster['PLAYER_NAME'].tolist() == ['Rhyne Howard', 'Bench Player']
    assert roster['TEAM_ID'].tolist() == [1611661330, 1611661330]

    stats = fallback.player_form_table(2026)
    rhyne = stats.loc[stats['PLAYER_NAME'].eq('Rhyne Howard')].iloc[0]
    assert rhyne['GP'] == 43
    assert rhyne['PTS'] == pytest.approx(17.7)
    assert rhyne['PRA'] == pytest.approx(25.2)
    assert rhyne['L5_GP'] == 3
    assert rhyne['L5_PTS'] == pytest.approx((8+12+5)/3)
    assert rhyne['LAST_GAME_DATE'] == '2026-10-19'
    assert rhyne['DATA_SOURCE'] == 'Basketball-Reference WNBA'

    pid = _stable_player_id('howarrh01w')
    log = fallback.player_game_log(pid, 2026)
    assert log['GAME_DATE'].dt.strftime('%Y-%m-%d').tolist() == ['2026-10-19','2026-10-17','2026-09-23']
    assert log[['PTS','REB','AST']].iloc[0].tolist() == [5.0,2.0,2.0]
    assert '2026-10-21' not in log['GAME_DATE'].dt.strftime('%Y-%m-%d').tolist()


def test_source_clean_generation_with_day_replaces_legacy_inputs_and_restores(monkeypatch):
    import sys, types, pandas as pd
    from wnba_pra_source_clean_guard_v1 import source_clean_generation

    players = types.ModuleType('wnba_players_v25')
    old = types.ModuleType('wnba_data_v232')
    old.PLAYER_HOSTS=('https://stats.wnba.com/stats/leaguedashplayerstats','https://stats.nba.com/stats/leaguedashplayerstats')
    original_roster=lambda *a,**k: pd.DataFrame({'ORIGINAL':[1]})
    original_form=lambda *a,**k: pd.DataFrame()
    original_log=lambda *a,**k: pd.DataFrame()
    players._espn_roster=original_roster
    players._espn_season_schedule=lambda *a,**k: pd.DataFrame({'ORIGINAL':[1]})
    players._espn_game_summary=lambda *a,**k: pd.DataFrame({'ORIGINAL':[1]})
    players.player_game_log=original_log
    old.player_form_table=original_form
    old.player_game_log=original_log
    monkeypatch.setitem(sys.modules,'wnba_players_v25',players)
    monkeypatch.setitem(sys.modules,'wnba_data_v232',old)

    class Fallback:
        def roster(self,*a,**k): return pd.DataFrame({'PLAYER_NAME':['Approved']})
        def player_form_table(self,*a,**k): return pd.DataFrame({'PLAYER_NAME':['Approved']})
        def player_game_log(self,*a,**k): return pd.DataFrame({'PTS':[1],'REB':[2],'AST':[3]})
    monkeypatch.setattr('wnba_pra_source_clean_guard_v1._make_reference_fallback', lambda *a,**k: Fallback())
    monkeypatch.setattr('wnba_pra_source_clean_guard_v1._make_first_party_fallback', lambda *a,**k: Fallback())

    with source_clean_generation('2026-10-21'):
        assert old.PLAYER_HOSTS == ('https://stats.wnba.com/stats/leaguedashplayerstats',)
        assert players._espn_roster(1)['PLAYER_NAME'].tolist() == ['Approved']
        assert old.player_form_table()['PLAYER_NAME'].tolist() == ['Approved']
        assert players.player_game_log(1)['PTS'].tolist() == [1]
        assert getattr(players._espn_season_schedule(), 'empty', False) is True
        assert getattr(players._espn_game_summary(), 'empty', False) is True
    assert old.PLAYER_HOSTS[1].startswith('https://stats.nba.com')
    assert players._espn_roster is original_roster
    assert old.player_form_table is original_form
    assert players.player_game_log is original_log


def test_preserved_artifact_generation_injects_official_schedule_and_live_pra_focus(monkeypatch):
    import types
    import pandas as pd
    import wnba_pra_page_model_artifact_v1 as artifact_mod

    captured = {}

    class Guard:
        blocked_calls = 0
    class Context:
        def __enter__(self): return Guard()
        def __exit__(self, *args): return False
    def fake_guard(day, season, **kwargs):
        captured['day'] = day
        captured['season'] = season
        captured.update(kwargs)
        return Context()

    bridge = types.SimpleNamespace(
        install=lambda: object(),
        restore=lambda token: None,
        market_snapshot=lambda day: {
            'player_props': pd.DataFrame([
                {'player_name':'Rhyne Howard','line':23.5},
                {'player_name':'Tiffany Hayes','line':14.5},
                {'player_name':'Rhyne Howard','line':23.5},
            ])
        },
    )
    schedule = {'games':[{'away':{'official_team_id':1,'team_tricode':'GSV','full_name':'Golden State Valkyries'},'home':{'official_team_id':2,'team_tricode':'ATL','full_name':'Atlanta Dream'}}]}
    class Client:
        def __init__(self, **kwargs): pass
        def games_for_date(self, day, season): return deepcopy(schedule)
    api_client = types.SimpleNamespace(KyreWNBAAPIClient=Client, PRA_VERCEL_BASE_URL='https://kyre-runless-proof.vercel.app')
    snapshot_module = types.SimpleNamespace(build_product_snapshot=lambda day: {'stored_mc_rows':[{'player':'Rhyne Howard','line':23.5}]})

    real_import = artifact_mod.importlib.import_module
    def fake_import(name):
        if name == 'wnba_pra_api_market_bridge_v2': return bridge
        if name == 'wnba_api_client_v1': return api_client
        if name == 'wnba_pra_product_snapshot_v1': return snapshot_module
        return real_import(name)

    monkeypatch.setattr(artifact_mod, 'source_clean_generation', fake_guard)
    monkeypatch.setattr(artifact_mod.importlib, 'import_module', fake_import)
    artifact_mod._build_preserved_snapshot('2026-10-21')

    assert captured['schedule_payload'] == schedule
    assert captured['focus_names'] == {'Rhyne Howard','Tiffany Hayes'}
    assert captured['day'] == '2026-10-21'
    assert captured['season'] == 2026


def test_reference_parser_survives_live_malformed_player_cell_close():
    from wnba_pra_source_clean_guard_v1 import _parse_rows
    html = """<table><tr class='full_table'><th data-stat='player'><strong><a href='/wnba/players/h/howarrh01w.html'>Rhyne Howard</a></strong</th><td data-stat='team'><a href='/wnba/teams/ATL/2026.html'>ATL</a></td><td data-stat='g'>43</td><td data-stat='pts_per_g'>17.7</td></tr></table>"""
    rows = _parse_rows(html)
    assert rows == [{
        'player':'Rhyne Howard', 'player__href':'/wnba/players/h/howarrh01w.html',
        'team':'ATL', 'team__href':'/wnba/teams/ATL/2026.html', 'g':'43', 'pts_per_g':'17.7'
    }]


def test_reference_game_log_skips_nat_date_rows():
    from wnba_pra_source_clean_guard_v1 import _ReferenceFallback, _stable_player_id

    season_html = """<table><tr><th data-stat='player'><a href='/wnba/players/h/howarrh01w.html'>Rhyne Howard</a></th><td data-stat='team'>ATL</td><td data-stat='g'>43</td><td data-stat='mp_per_g'>34.2</td><td data-stat='pts_per_g'>17.7</td><td data-stat='trb_per_g'>3.8</td><td data-stat='ast_per_g'>3.7</td></tr></table>"""
    log_html = """<table><tr><th data-stat='date_game'>NaT</th><td data-stat='team_id'>ATL</td><td data-stat='opp_id'>GSV</td><td data-stat='mp'>0:00</td><td data-stat='pts'>0</td><td data-stat='trb'>0</td><td data-stat='ast'>0</td></tr><tr><th data-stat='date_game'>2026-10-19</th><td data-stat='team_id'>ATL</td><td data-stat='opp_id'>GSV</td><td data-stat='mp'>27:00</td><td data-stat='pts'>5</td><td data-stat='trb'>2</td><td data-stat='ast'>2</td></tr></table>"""
    class Response:
        status_code = 200
        def __init__(self, text): self.text = text
    class Session:
        def get(self, url, *, headers, timeout):
            if url.endswith('/wnba/years/2026_per_game.html'): return Response(season_html)
            if url.endswith('/wnba/players/h/howarrh01w/gamelog/2026/'): return Response(log_html)
            if url.endswith('/wnba/players/h/howarrh01w/gamelog-playoffs/'): return Response('<table></table>')
            return Response('<table></table>')
    fallback = _ReferenceFallback('2026-10-21', 2026, session=Session(), schedule_payload={'games':[]}, focus_names={'Rhyne Howard'})
    fallback._season()
    log = fallback.player_game_log(_stable_player_id('howarrh01w'), 2026)
    assert len(log) == 1
    assert log.iloc[0]['GAME_DATE'].strftime('%Y-%m-%d') == '2026-10-19'


def test_official_first_party_fallback_preserves_ids_season_rates_and_recent_minutes():
    from wnba_pra_source_clean_guard_v1 import _FirstPartyFallback

    roster_dataset = {
        'players': [
            {'player_id': 1631009, 'full_name': 'Rhyne Howard', 'official_team_id': 1611661330, 'team_name': 'Dream', 'team_abbreviation': 'ATL', 'position': 'Guard', 'is_current_roster': True},
            {'player_id': 203026, 'full_name': 'Tiffany Hayes', 'official_team_id': 1611661331, 'team_name': 'Valkyries', 'team_abbreviation': 'GSV', 'position': 'Guard', 'is_current_roster': True},
        ]
    }
    pages = {
        1631009: {'stats': {'PTS': 17.7, 'REB': 3.8, 'AST': 3.7}},
        203026: {'stats': {'PTS': 8.6, 'REB': 2.5, 'AST': 2.1}},
    }
    histories = {
        1631009: [
            {'game_date':'2026-10-19','minutes':27.0,'points':5,'rebounds':2,'assists':2},
            {'game_date':'2026-10-17','minutes':38.0,'points':12,'rebounds':7,'assists':4},
            {'game_date':'2026-10-09','minutes':38.0,'points':21,'rebounds':2,'assists':0},
            {'game_date':'2026-10-07','minutes':36.0,'points':18,'rebounds':4,'assists':5},
            {'game_date':'2026-10-05','minutes':35.0,'points':17,'rebounds':3,'assists':4},
        ],
        203026: [
            {'game_date':'2026-10-19','minutes':25.0,'points':14,'rebounds':2,'assists':3},
            {'game_date':'2026-10-17','minutes':27.0,'points':8,'rebounds':3,'assists':2},
            {'game_date':'2026-10-09','minutes':29.0,'points':10,'rebounds':4,'assists':1},
            {'game_date':'2026-10-07','minutes':24.0,'points':7,'rebounds':2,'assists':3},
            {'game_date':'2026-10-05','minutes':22.0,'points':5,'rebounds':1,'assists':2},
        ],
    }
    def roster_loader(season, current_roster_only=True):
        assert season == 2026 and current_roster_only is True
        return deepcopy(roster_dataset)
    def page_loader(player_id):
        return ({}, deepcopy(pages[player_id]), 'stamp', False, 120, f'https://www.wnba.com/player/{player_id}')
    def history_loader(player_id, season, season_type='Regular Season'):
        games = histories[player_id] if season_type == 'Playoffs' else []
        return {'games': deepcopy(games)}

    schedule = {'games':[{'away':{'official_team_id':1611661331,'full_name':'Golden State Valkyries','team_tricode':'GSV'},'home':{'official_team_id':1611661330,'full_name':'Atlanta Dream','team_tricode':'ATL'}}]}
    fallback = _FirstPartyFallback('2026-10-21', 2026, schedule_payload=schedule, focus_names={'Rhyne Howard','Tiffany Hayes'}, roster_loader=roster_loader, player_page_loader=page_loader, history_loader=history_loader)
    atl = fallback.roster(1611661330, 'Atlanta Dream', 'ATL')
    assert atl[['PLAYER_ID','PLAYER_NAME']].to_dict('records') == [{'PLAYER_ID':1631009,'PLAYER_NAME':'Rhyne Howard'}]

    form = fallback.player_form_table(2026)
    rhyne = form[form['PLAYER_ID'].eq(1631009)].iloc[0]
    assert rhyne['PTS'] == pytest.approx(17.7)
    assert rhyne['REB'] == pytest.approx(3.8)
    assert rhyne['AST'] == pytest.approx(3.7)
    assert rhyne['PRA'] == pytest.approx(25.2)
    assert rhyne['GP'] == 5
    assert rhyne['MIN'] == pytest.approx((27+38+38+36+35)/5)
    assert rhyne['L5_MIN'] == pytest.approx(rhyne['MIN'])
    assert rhyne['L5_PTS'] == pytest.approx((5+12+21+18+17)/5)
    assert rhyne['LAST_GAME_DATE'] == '2026-10-19'
    assert rhyne['DATA_SOURCE'] == 'WNBA.com First-Party Page Data'

    log = fallback.player_game_log(1631009, 2026)
    assert len(log) == 5
    assert log.iloc[0][['PTS','REB','AST']].tolist() == [5.0,2.0,2.0]
    zero_ast = log[log['GAME_DATE'].dt.strftime('%Y-%m-%d').eq('2026-10-09')].iloc[0]
    assert zero_ast['AST'] == 0.0


def test_source_clean_context_preloads_data_module_and_prefers_official_first_party(monkeypatch):
    import types, sys, pandas as pd
    import wnba_pra_source_clean_guard_v1 as guard

    players = types.ModuleType('wnba_players_v25')
    players._espn_roster = lambda *a, **k: pd.DataFrame()
    players._espn_season_schedule = lambda *a, **k: pd.DataFrame()
    players._espn_game_summary = lambda *a, **k: pd.DataFrame()
    players.player_game_log = lambda *a, **k: pd.DataFrame()
    data = types.ModuleType('wnba_data_v232')
    data.player_form_table = lambda *a, **k: pd.DataFrame({'ORIGINAL':[1]})
    data.player_game_log = lambda *a, **k: pd.DataFrame()
    data.PLAYER_HOSTS = ('https://stats.wnba.com/stats/leaguedashplayerstats','https://stats.nba.com/stats/leaguedashplayerstats')
    monkeypatch.setitem(sys.modules, 'wnba_players_v25', players)
    monkeypatch.delitem(sys.modules, 'wnba_data_v232', raising=False)

    class Official:
        def roster(self,*a,**k): return pd.DataFrame({'PLAYER_NAME':['Official']})
        def player_form_table(self,*a,**k): return pd.DataFrame({'PLAYER_NAME':['Official']})
        def player_game_log(self,*a,**k): return pd.DataFrame({'PTS':[1]})
    monkeypatch.setattr(guard, '_make_first_party_fallback', lambda *a,**k: Official())
    real_import = guard.importlib.import_module
    def fake_import(name):
        if name == 'wnba_players_v25': return players
        if name == 'wnba_data_v232':
            sys.modules[name] = data
            return data
        return real_import(name)
    monkeypatch.setattr(guard.importlib, 'import_module', fake_import)

    with guard.source_clean_generation('2026-10-21', 2026, schedule_payload={'games':[]}, focus_names={'Official'}):
        assert data.player_form_table()['PLAYER_NAME'].tolist() == ['Official']
        assert players._espn_roster(1)['PLAYER_NAME'].tolist() == ['Official']
        assert players.player_game_log(1)['PTS'].tolist() == [1]
        assert data.PLAYER_HOSTS == ('https://stats.wnba.com/stats/leaguedashplayerstats',)


def test_lightweight_artifact_validation_requires_exact_hash_without_heavy_model_import():
    import sys
    from runless_v2.wnba_pra_page_snapshot_v1 import validate_artifact_light
    artifact = _artifact()
    artifact.update({
        "model_version":"PRA V3.6.17",
        "generated_at":"2026-10-21T19:20:05+00:00",
        "rows":[],"line_bindings":{},"final_card":[],
    })
    import hashlib, json
    raw=dict(artifact); raw.pop("content_hash",None)
    artifact["content_hash"]="sha256:"+hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
    before=set(sys.modules)
    out=validate_artifact_light(artifact)
    after=set(sys.modules)
    assert out["content_hash"] == artifact["content_hash"]
    assert "wnba_pra_page_model_artifact_v1" not in (after-before)
    broken=deepcopy(artifact); broken["rows"]=[{"player_name":"tampered"}]
    with pytest.raises(ValueError, match="content hash"):
        validate_artifact_light(broken)


def test_server_owned_refresh_skips_fresh_and_single_flights_needed_refresh():
    import runless_v2.wnba_pra_page_snapshot_v1 as route

    class Store:
        def __init__(self): self.claims=0; self.published=0
        def claim_refresh(self, **kwargs): self.claims += 1; return {"acquired":True,"lease_token":"lease-1"}
        def publish_with_lease(self, artifact, **kwargs): self.published += 1; return {"stored":True,"content_hash":artifact["content_hash"]}
        def release_refresh(self, **kwargs): return {"released":True}
    artifact={"schema_version":"wnba_pra_page_model_artifact_v1","date":"2026-10-21","season":2026,"generated_at":"2026-10-21T19:30:00+00:00","model_version":"PRA V3.6.17","rows":[],"line_bindings":{},"final_card":[]}
    import hashlib,json
    raw=dict(artifact); artifact["content_hash"]="sha256:"+hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()

    fresh_store=Store()
    fresh=route.refresh_snapshot_server_owned(
        date="2026-10-21", season=2026, store=fresh_store,
        page_state_builder=lambda **_: {"snapshot_state":"READY","cache_state":"FRESH","refresh_required":False},
        artifact_builder=lambda *_: (_ for _ in ()).throw(AssertionError("fresh must not build")),
    )
    assert fresh["state"] == "NOT_NEEDED"
    assert fresh_store.claims == 0

    needed_store=Store(); builds=[]
    needed=route.refresh_snapshot_server_owned(
        date="2026-10-21", season=2026, store=needed_store,
        page_state_builder=lambda **_: {"snapshot_state":"MODEL_REFRESH_REQUIRED","cache_state":"FRESH","refresh_required":True},
        artifact_builder=lambda d,s: builds.append((d,s)) or deepcopy(artifact),
    )
    assert needed["state"] == "REFRESHED"
    assert needed_store.claims == 1 and needed_store.published == 1
    assert builds == [("2026-10-21",2026)]
