from __future__ import annotations

import base64
import hashlib
import json
from types import ModuleType
from typing import Any, Mapping

import httpx

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

BASE_SHA = "c038037f0c7f9e1a6338c2ca29bdcae08e15fae7"
CANDIDATE_SHA = "6bfe5a42f08cb2c20b4ce3efa5dd6b3e8bc75e56"
PR_NUMBER = 1424
API_BASE = "https://kyre-sports-api.onrender.com"
EXPECTED_FILES = tuple(sorted((
    "wnba_pra_game_center_v2_step3.py",
    "wnba_pra_game_center_stats_hydration_v1.py",
    "tests/test_wnba_data_step2_live_hydration.py",
)))


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _content(client, path: str) -> tuple[str, str]:
    item = client.content(path, ref=CANDIDATE_SHA)
    if not item or item.get("encoding") != "base64":
        raise RuntimeError("WNBA_LIVE_HYDRATION_FILE_READ_FAILED:" + path)
    return base64.b64decode(item["content"]).decode(), str(item.get("sha") or "")


def _verify_identity_and_scope(client) -> dict[str, str]:
    if client.branch_sha("main") != BASE_SHA:
        raise RuntimeError("WAIT_MAIN_SHA_DRIFT")
    pr = client.request("GET", f"/pulls/{PR_NUMBER}") or {}
    if str((pr.get("head") or {}).get("sha") or "") != CANDIDATE_SHA:
        raise RuntimeError("WNBA_LIVE_HYDRATION_PR_HEAD_DRIFT")
    if str((pr.get("base") or {}).get("sha") or "") != BASE_SHA:
        raise RuntimeError("WNBA_LIVE_HYDRATION_PR_BASE_DRIFT")
    if str(pr.get("state") or "") != "open":
        raise RuntimeError("WNBA_LIVE_HYDRATION_PR_NOT_OPEN")

    files = client.request("GET", f"/pulls/{PR_NUMBER}/files?per_page=100") or []
    changed = tuple(sorted(str(item.get("filename") or "") for item in files))
    if changed != EXPECTED_FILES:
        raise RuntimeError("WNBA_LIVE_HYDRATION_SCOPE_DRIFT:" + ",".join(changed))

    tree = client.tree_blobs(CANDIDATE_SHA)
    artifacts = {path: str(tree.get(path) or "") for path in EXPECTED_FILES}
    if any(len(blob) != 40 for blob in artifacts.values()):
        raise RuntimeError("WNBA_LIVE_HYDRATION_ARTIFACT_MISSING")
    return artifacts


def _load_helper(client):
    source, _ = _content(client, "wnba_pra_game_center_stats_hydration_v1.py")
    compile(source, "wnba_pra_game_center_stats_hydration_v1.py", "exec")
    module = ModuleType("wnba_pra_game_center_stats_hydration_v1")
    exec(compile(source, module.__name__ + ".py", "exec"), module.__dict__)
    return module, source


def _verify_source_contract(client, helper_source: str) -> dict[str, Any]:
    game_source, _ = _content(client, "wnba_pra_game_center_v2_step3.py")
    test_source, _ = _content(client, "tests/test_wnba_data_step2_live_hydration.py")
    compile(game_source, "wnba_pra_game_center_v2_step3.py", "exec")
    compile(test_source, "tests/test_wnba_data_step2_live_hydration.py", "exec")

    required_game_tokens = (
        "/api/v1/wnba/stats/players",
        "hydrate_zero_production_rows",
        "is_zero_production_candidate",
        "fake_zero_production_allowed\": False",
        "Observed WNBA player production is unavailable; fake zero production was blocked.",
    )
    missing = [token for token in required_game_tokens if token not in game_source]
    if missing:
        raise RuntimeError("WNBA_LIVE_HYDRATION_GAME_CONTRACT_MISSING:" + "|".join(missing))
    if "WNBA Stats via Kyre Sports API" not in helper_source:
        raise RuntimeError("WNBA_LIVE_HYDRATION_ID_SOURCE_CONTRACT_MISSING")
    return {
        "game_source_sha256": hashlib.sha256(game_source.encode()).hexdigest(),
        "helper_source_sha256": hashlib.sha256(helper_source.encode()).hexdigest(),
        "test_source_sha256": hashlib.sha256(test_source.encode()).hexdigest(),
    }


def _api_payload(last_n: int) -> dict[str, Any]:
    response = httpx.get(
        API_BASE + "/api/v1/wnba/stats/players",
        params={
            "season": 2026,
            "season_type": "Regular Season",
            "last_n_games": int(last_n),
            "per_mode": "PerGame",
        },
        timeout=30.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or body.get("data_type") != "official_player_season_statistics":
        raise RuntimeError(f"WNBA_LIVE_HYDRATION_API_SCHEMA_{last_n}")
    if int(body.get("player_count") or 0) <= 0 or not isinstance(body.get("players"), list):
        raise RuntimeError(f"WNBA_LIVE_HYDRATION_API_EMPTY_{last_n}")
    return body


def _positive(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _verify_real_hydration(helper) -> dict[str, Any]:
    season = _api_payload(0)
    l10 = _api_payload(10)
    l5 = _api_payload(5)
    l10_keys = {(int(p.get("official_team_id") or 0), str(p.get("player_name") or "").casefold()) for p in l10["players"]}
    l5_keys = {(int(p.get("official_team_id") or 0), str(p.get("player_name") or "").casefold()) for p in l5["players"]}

    sample = None
    for player in season["players"]:
        stats = player.get("stats") if isinstance(player.get("stats"), Mapping) else {}
        key = (int(player.get("official_team_id") or 0), str(player.get("player_name") or "").casefold())
        if (
            int(player.get("player_id") or 0) > 0
            and key in l10_keys
            and key in l5_keys
            and _positive(stats.get("minutes"))
            and any(_positive(stats.get(field)) for field in ("points", "rebounds", "assists"))
        ):
            sample = player
            break
    if sample is None:
        raise RuntimeError("WNBA_LIVE_HYDRATION_NO_POSITIVE_REAL_SAMPLE")

    zero = {
        "PLAYER_ID": 999999999,
        "PLAYER_NAME": sample["player_name"],
        "TEAM_ID": sample["official_team_id"],
        "TEAM_ABBREVIATION": sample.get("team_abbreviation") or "",
        "MIN": 0.0,
        "PTS": 0.0,
        "REB": 0.0,
        "AST": 0.0,
        "PRA": 0.0,
        "DATA_SOURCE": "Current roster • no matched production row",
        "PLAYER_ID_SOURCE": "ESPN",
    }
    rows, diag = helper.hydrate_zero_production_rows(
        [zero],
        season_payload=season,
        l10_payload=l10,
        l5_payload=l5,
        allowed_team_ids={int(sample["official_team_id"])},
    )
    if diag != {"candidates": 1, "hydrated": 1, "unresolved": 0}:
        raise RuntimeError("WNBA_LIVE_HYDRATION_REAL_DIAG_FAILED")
    row = rows[0]
    if int(row.get("PLAYER_ID") or 0) != int(sample["player_id"]):
        raise RuntimeError("WNBA_LIVE_HYDRATION_REAL_ID_FAILED")
    if not _positive(row.get("MIN")):
        raise RuntimeError("WNBA_LIVE_HYDRATION_REAL_MINUTES_FAILED")
    if not any(_positive(row.get(field)) for field in ("PTS", "REB", "AST")):
        raise RuntimeError("WNBA_LIVE_HYDRATION_REAL_PRA_INPUTS_FAILED")
    return {
        "sample_player_id": int(row["PLAYER_ID"]),
        "sample_player_name": str(row.get("PLAYER_NAME") or ""),
        "sample_team_id": int(row.get("TEAM_ID") or 0),
        "sample_min": float(row.get("MIN") or 0),
        "sample_pts": float(row.get("PTS") or 0),
        "sample_reb": float(row.get("REB") or 0),
        "sample_ast": float(row.get("AST") or 0),
        "season_player_count": int(season.get("player_count") or 0),
        "l10_player_count": int(l10.get("player_count") or 0),
        "l5_player_count": int(l5.get("player_count") or 0),
    }


def run_gate(client):
    artifacts = _verify_identity_and_scope(client)
    helper, helper_source = _load_helper(client)
    source_proof = _verify_source_contract(client, helper_source)

    # Synthetic contract: preserve real production and hydrate only zero fallback.
    payload = {
        "data_type": "official_player_season_statistics",
        "players": [{
            "player_id": 204319,
            "player_name": "Rebecca Allen",
            "official_team_id": 1611661332,
            "team_abbreviation": "TOR",
            "games_played": 20,
            "stats": {"minutes": 26.4, "points": 10.8, "rebounds": 3.1, "assists": 2.2},
        }],
    }
    hydrated, diag = helper.hydrate_zero_production_rows(
        [{"PLAYER_ID": 999999, "PLAYER_NAME": "Rebecca Allen", "TEAM_ID": 1611661332,
          "MIN": 0.0, "PTS": 0.0, "REB": 0.0, "AST": 0.0, "PRA": 0.0,
          "DATA_SOURCE": "Current roster • no matched production row", "PLAYER_ID_SOURCE": "ESPN"}],
        season_payload=payload,
        l10_payload=payload,
        l5_payload=payload,
        allowed_team_ids={1611661332},
    )
    if diag != {"candidates": 1, "hydrated": 1, "unresolved": 0} or float(hydrated[0]["MIN"]) != 26.4:
        raise RuntimeError("WNBA_LIVE_HYDRATION_SYNTHETIC_CONTRACT_FAILED")

    live_api_proof = _verify_real_hydration(helper)
    evidence = {
        "candidate_sha": CANDIDATE_SHA,
        "pr": PR_NUMBER,
        "files": list(EXPECTED_FILES),
        "artifacts": artifacts,
        "source_proof": source_proof,
        "live_api_proof": live_api_proof,
        "root_cause": "roster-only zero-production rows reached the frozen role engine and triggered equal-share 200-team-minute fallback",
        "patch": "hydrate only zero-production WNBA PRA Game Center rows from hosted official season/L10/L5 stats and fail closed on unresolved fake zeros",
        "other_sports_changed": 0,
        "navigation_changed": False,
        "role_math_changed": False,
        "projection_math_changed": False,
        "sportsbook_changed": False,
        "github_actions_fallback": False,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-data-step2-live-hydration-{CANDIDATE_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step2-live-hydration",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step2",
        step="2/5-live-hydration-candidate",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=artifacts,
        dependency_map={"base_main_sha": BASE_SHA, "pr_number": PR_NUMBER, "github_actions_fallback": False},
        registry_before={"existing_step2_freeze": "historical_checkpoint_preserved"},
        registry_after={"mode": "candidate_gate_only_no_registry_mutation"},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": int(check["id"]),
        "receipt": str(receipt["digest"]),
        "live_api_proof": live_api_proof,
        "artifacts": artifacts,
    }


def install_startup_gate(app):
    app.state.wnba_data_step2_live_hydration_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _gate():
        try:
            app.state.wnba_data_step2_live_hydration_gate = run_gate(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step2_live_hydration_gate = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1000],
            }
            print("WNBA_DATA_STEP2_LIVE_HYDRATION_GATE_FAIL=" + json.dumps(app.state.wnba_data_step2_live_hydration_gate, sort_keys=True), flush=True)
            return
        print("WNBA_DATA_STEP2_LIVE_HYDRATION_GATE_GREEN=" + json.dumps(app.state.wnba_data_step2_live_hydration_gate, sort_keys=True), flush=True)

    return app
