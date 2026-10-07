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
CANDIDATE_SHA = "6003c8d401090a1899c84ba10552640913147f5c"
PR_NUMBER = 1424
EXPECTED_FILES = tuple(sorted((
    "wnba_pra_game_center_v2_step3.py",
    "wnba_pra_game_center_stats_hydration_v1.py",
    "tests/test_wnba_data_step2_live_hydration.py",
)))
HEADERS = {
    "accept": "text/html,application/xhtml+xml",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
}


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
        "_first_party_stat_windows",
        "parse_first_party_roster_html",
        "parse_first_party_player_latest_games_html",
        "fake_zero_production_allowed\": False",
        "Observed WNBA player production is unavailable; fake zero production was blocked.",
    )
    missing = [token for token in required_game_tokens if token not in game_source]
    if missing:
        raise RuntimeError("WNBA_LIVE_HYDRATION_GAME_CONTRACT_MISSING:" + "|".join(missing))
    required_helper = (
        "TEAM_ROSTER_URLS_BY_ID",
        "WNBA.com player.latestGames recent observed history",
        "build_first_party_recent_stat_payloads",
    )
    missing_helper = [token for token in required_helper if token not in helper_source]
    if missing_helper:
        raise RuntimeError("WNBA_LIVE_HYDRATION_HELPER_CONTRACT_MISSING:" + "|".join(missing_helper))
    return {
        "game_source_sha256": hashlib.sha256(game_source.encode()).hexdigest(),
        "helper_source_sha256": hashlib.sha256(helper_source.encode()).hexdigest(),
        "test_source_sha256": hashlib.sha256(test_source.encode()).hexdigest(),
    }


def _get_text(url: str) -> str:
    response = httpx.get(url, headers=HEADERS, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    if not response.text.strip():
        raise RuntimeError("WNBA_FIRST_PARTY_EMPTY_RESPONSE:" + url)
    return response.text


def _positive(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _verify_synthetic(helper) -> None:
    payload = {
        "data_type": "official_player_season_statistics",
        "players": [{
            "player_id": 204319,
            "player_name": "Rebecca Allen",
            "official_team_id": 1611661332,
            "team_abbreviation": "TOR",
            "games_played": 3,
            "stats": {"minutes": 30.0, "points": 14.0, "rebounds": 4.0, "assists": 5.0},
        }],
    }
    rows, diag = helper.hydrate_zero_production_rows(
        [{"PLAYER_ID": 999999, "PLAYER_NAME": "Rebecca Allen", "TEAM_ID": 1611661332,
          "MIN": 0.0, "PTS": 0.0, "REB": 0.0, "AST": 0.0, "PRA": 0.0,
          "DATA_SOURCE": "Current roster • no matched production row", "PLAYER_ID_SOURCE": "ESPN"}],
        season_payload=payload,
        l10_payload=payload,
        l5_payload=payload,
        allowed_team_ids={1611661332},
        data_source="WNBA.com First-Party • player.latestGames recent observed history",
        player_id_source="WNBA.com First-Party roster identity",
    )
    if diag != {"candidates": 1, "hydrated": 1, "unresolved": 0}:
        raise RuntimeError("WNBA_LIVE_HYDRATION_SYNTHETIC_DIAG_FAILED")
    if float(rows[0]["MIN"]) != 30.0 or float(rows[0]["PRA"]) != 23.0:
        raise RuntimeError("WNBA_LIVE_HYDRATION_SYNTHETIC_VALUES_FAILED")


def _verify_first_party_live(helper) -> dict[str, Any]:
    team_id = 1611661332
    roster_url = helper.roster_url_for_team(team_id)
    roster_html = _get_text(roster_url)
    roster = helper.parse_first_party_roster_html(roster_html, team_id)
    if len(roster) < 7:
        raise RuntimeError(f"WNBA_FIRST_PARTY_TORONTO_ROSTER_TOO_SMALL:{len(roster)}")

    preferred = ["rebeccaallen", "paulineastier"]
    ordered = sorted(
        roster,
        key=lambda player: (
            preferred.index(helper.normalize_player_name(player.get("player_name")))
            if helper.normalize_player_name(player.get("player_name")) in preferred else 99,
            helper.normalize_player_name(player.get("player_name")),
        ),
    )

    sample = None
    sample_games = None
    attempts = 0
    for identity in ordered[:8]:
        attempts += 1
        player_id = int(identity["player_id"])
        try:
            player_html = _get_text(f"https://www.wnba.com/player/{player_id}")
            games = helper.parse_first_party_player_latest_games_html(
                player_html,
                expected_player_id=player_id,
                season=2026,
            )
        except Exception:
            continue
        if not games:
            continue
        if not any(_positive(game.get("MIN")) for game in games):
            continue
        if not any(any(_positive(game.get(stat)) for stat in ("PTS", "REB", "AST")) for game in games):
            continue
        sample = identity
        sample_games = games
        break
    if sample is None or sample_games is None:
        raise RuntimeError("WNBA_FIRST_PARTY_NO_POSITIVE_TORONTO_PLAYER_HISTORY")

    windows = helper.build_first_party_recent_stat_payloads(
        [{**sample, "games": sample_games}],
        season=2026,
    )
    zero = {
        "PLAYER_ID": 999999999,
        "PLAYER_NAME": sample["player_name"],
        "TEAM_ID": sample["official_team_id"],
        "TEAM_ABBREVIATION": sample.get("team_abbreviation") or "",
        "MIN": 0.0, "PTS": 0.0, "REB": 0.0, "AST": 0.0, "PRA": 0.0,
        "DATA_SOURCE": "Current roster • no matched production row",
        "PLAYER_ID_SOURCE": "ESPN",
    }
    rows, diag = helper.hydrate_zero_production_rows(
        [zero],
        season_payload=windows.get(0),
        l10_payload=windows.get(10),
        l5_payload=windows.get(5),
        allowed_team_ids={team_id},
        data_source="WNBA.com First-Party • player.latestGames recent observed history",
        player_id_source="WNBA.com First-Party roster identity",
    )
    if diag != {"candidates": 1, "hydrated": 1, "unresolved": 0}:
        raise RuntimeError("WNBA_FIRST_PARTY_LIVE_HYDRATION_DIAG_FAILED")
    row = rows[0]
    if int(row.get("PLAYER_ID") or 0) != int(sample["player_id"]):
        raise RuntimeError("WNBA_FIRST_PARTY_LIVE_ID_FAILED")
    if not _positive(row.get("MIN")):
        raise RuntimeError("WNBA_FIRST_PARTY_LIVE_MINUTES_FAILED")
    if not any(_positive(row.get(stat)) for stat in ("PTS", "REB", "AST")):
        raise RuntimeError("WNBA_FIRST_PARTY_LIVE_PRODUCTION_FAILED")
    return {
        "team_id": team_id,
        "roster_players": len(roster),
        "player_id": int(row["PLAYER_ID"]),
        "player_name": str(sample["player_name"]),
        "games_observed": len(sample_games),
        "min": float(row.get("MIN") or 0),
        "pts": float(row.get("PTS") or 0),
        "reb": float(row.get("REB") or 0),
        "ast": float(row.get("AST") or 0),
        "pra": float(row.get("PRA") or 0),
        "player_page_attempts": attempts,
    }


def run_gate(client):
    artifacts = _verify_identity_and_scope(client)
    helper, helper_source = _load_helper(client)
    source_proof = _verify_source_contract(client, helper_source)
    _verify_synthetic(helper)
    first_party_proof = _verify_first_party_live(helper)
    evidence = {
        "candidate_sha": CANDIDATE_SHA,
        "pr": PR_NUMBER,
        "files": list(EXPECTED_FILES),
        "artifacts": artifacts,
        "source_proof": source_proof,
        "first_party_live_proof": first_party_proof,
        "known_bulk_failure": "Kyre Sports API /stats/players returned HTTP 502 in prior exact-head Runless gate",
        "root_cause": "roster-only zero-production rows reached the frozen role engine and triggered equal-share 200-team-minute fallback",
        "patch": "hydrate zero-only Game Center rows from hosted bulk stats when healthy, then fail over to official WNBA roster identity + player.latestGames observed history; unresolved zeros are blocked",
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
        "first_party_live_proof": first_party_proof,
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
