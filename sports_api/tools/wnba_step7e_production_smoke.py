#!/usr/bin/env python3
"""Step 7E: outside-in production smoke test for the hosted WNBA API.

This operator only performs HTTPS GET requests against the deployed Render API.
It does not mutate Render, Supabase, GitHub, environment variables, durable
storage, sportsbook state, or scheduler state.  The smoke test verifies the
public API surface, frozen architecture certificate, Supabase configuration
readiness, pre-activation safety state, and one official WNBA schedule read.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import time
from typing import Any, Callable, Mapping

import httpx

MODEL_VERSION = "wnba_step_7e_production_smoke_v1"
BASE_URL = "https://kyre-sports-api.onrender.com"
EXPECTED_SUPABASE_HOST = "jqajcdckalsfizbvngiu.supabase.co"
EXPECTED_RELEASE_REVISION = "12b9a0bb21e72f16282f562d848673222d48c7f2"

CRITICAL_OPENAPI_PATHS = {
    "/health",
    "/api/v1/wnba/teams",
    "/api/v1/wnba/league",
    "/api/v1/wnba/games/today",
    "/api/v1/wnba/runtime/step6r-supabase-storage",
    "/api/v1/wnba/runtime/step6t-canary-evidence/status",
    "/api/v1/wnba/runtime/step6u-activation-bridge/status",
    "/api/v1/wnba/runtime/step6w-final-certification",
}


class Step7ESmokeError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe_summary(body: Any) -> dict[str, Any]:
    if not isinstance(body, Mapping):
        return {"json_object": False}
    interesting = (
        "name", "version", "status", "data_type", "season", "team_count",
        "game_count", "selected_backend", "configuration_ready", "bridge_ready",
        "scheduler_authorized", "final_architecture_certified", "production_live",
        "state", "source",
    )
    out = {key: body.get(key) for key in interesting if key in body}
    out["json_object"] = True
    return out


def _get_json(
    client: httpx.Client,
    path: str,
    *,
    timeout_seconds: float = 150.0,
    acceptable_statuses: tuple[int, ...] = (200,),
) -> tuple[int, Any, int, float]:
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    started = time.monotonic()
    last_status: int | None = None
    last_detail = "not attempted"
    while True:
        attempts += 1
        try:
            response = client.get(BASE_URL + path)
            last_status = response.status_code
            if response.status_code in acceptable_statuses:
                try:
                    body = response.json()
                except ValueError as exc:
                    raise Step7ESmokeError(f"{path} returned non-JSON HTTP {response.status_code}.") from exc
                return response.status_code, body, attempts, round(time.monotonic() - started, 3)
            last_detail = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_detail = f"{type(exc).__name__}: {exc}"
        if time.monotonic() >= deadline:
            raise Step7ESmokeError(
                f"Timed out waiting for {path}; last_status={last_status!r}; detail={last_detail}"
            )
        time.sleep(4)


def _assert_dict(body: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(body, Mapping):
        raise Step7ESmokeError(f"{label} response must be a JSON object.")
    return body


def validate_health(body: Any) -> None:
    doc = _assert_dict(body, "health")
    if doc.get("status") != "ok":
        raise Step7ESmokeError("Hosted /health did not report status=ok.")


def validate_root(body: Any) -> None:
    doc = _assert_dict(body, "root")
    if doc.get("name") != "Kyre Sports API" or doc.get("status") != "online":
        raise Step7ESmokeError("Hosted root identity/status is invalid.")


def validate_openapi(body: Any) -> None:
    doc = _assert_dict(body, "OpenAPI")
    paths = doc.get("paths")
    if not isinstance(paths, Mapping):
        raise Step7ESmokeError("OpenAPI document has no paths object.")
    missing = sorted(CRITICAL_OPENAPI_PATHS.difference(paths))
    if missing:
        raise Step7ESmokeError(f"Hosted OpenAPI is missing critical WNBA paths: {missing}")
    if len(paths) < 25:
        raise Step7ESmokeError(f"Hosted OpenAPI path count is unexpectedly small: {len(paths)}")


def validate_teams(body: Any) -> None:
    doc = _assert_dict(body, "teams")
    teams = doc.get("teams")
    try:
        count = int(doc.get("team_count"))
    except (TypeError, ValueError) as exc:
        raise Step7ESmokeError("WNBA teams endpoint has invalid team_count.") from exc
    if doc.get("season") != 2026 or not isinstance(teams, list) or count != len(teams) or count < 13:
        raise Step7ESmokeError("WNBA teams endpoint failed 2026 league-registry sanity checks.")


def validate_league(body: Any) -> None:
    doc = _assert_dict(body, "league")
    if doc.get("season") != 2026:
        raise Step7ESmokeError("WNBA league endpoint did not return the 2026 league.")


def validate_step6r(body: Any) -> None:
    doc = _assert_dict(body, "Step 6R")
    backend = doc.get("backend") if isinstance(doc.get("backend"), Mapping) else {}
    if doc.get("selected_backend") != "supabase" or doc.get("configuration_ready") is not True:
        raise Step7ESmokeError("Hosted Step 6R does not report Supabase configuration ready.")
    if backend.get("project_host") != EXPECTED_SUPABASE_HOST:
        raise Step7ESmokeError("Hosted Step 6R points at the wrong Supabase project.")
    if backend.get("secret_configured") is not True or backend.get("secret_value_exposed") is not False:
        raise Step7ESmokeError("Hosted Step 6R secret-safety flags are invalid.")


def validate_step6t(body: Any) -> None:
    doc = _assert_dict(body, "Step 6T")
    if doc.get("selected_backend") != "supabase" or doc.get("configuration_ready") is not True:
        raise Step7ESmokeError("Hosted Step 6T is not ready for Supabase evidence verification.")
    if doc.get("verification_requires_network") is not True or doc.get("verification_is_read_only") is not True:
        raise Step7ESmokeError("Hosted Step 6T verification semantics are invalid.")
    if doc.get("scheduler_authorized") is not False:
        raise Step7ESmokeError("Hosted Step 6T unexpectedly authorizes the scheduler.")


def validate_step6u(body: Any) -> None:
    doc = _assert_dict(body, "Step 6U")
    if doc.get("selected_backend") != "supabase" or doc.get("configuration_ready") is not True:
        raise Step7ESmokeError("Hosted Step 6U bridge configuration is not ready.")
    if doc.get("bridge_ready") is not False or doc.get("verification_required") is not True:
        raise Step7ESmokeError("Hosted Step 6U should remain pre-activation and verification-required.")
    if doc.get("scheduler_authorized") is not False:
        raise Step7ESmokeError("Hosted Step 6U unexpectedly authorizes the scheduler.")
    safety = doc.get("safety") if isinstance(doc.get("safety"), Mapping) else {}
    if safety.get("production_runtime_enabled") is not False or safety.get("scheduler_started") is not False:
        raise Step7ESmokeError("Hosted Step 6U production/scheduler safety state is invalid.")


def validate_step6w(body: Any) -> None:
    doc = _assert_dict(body, "Step 6W")
    if doc.get("final_architecture_certified") is not True:
        raise Step7ESmokeError("Hosted Step 6W final architecture certificate is not green.")
    if doc.get("state") != "wnba_upgraded_architecture_frozen":
        raise Step7ESmokeError("Hosted Step 6W freeze state is invalid.")
    if doc.get("production_live") is not False or doc.get("scheduler_authorized") is not False:
        raise Step7ESmokeError("Hosted Step 6W incorrectly claims production/scheduler activation.")


def validate_games_today(body: Any) -> None:
    doc = _assert_dict(body, "games today")
    if doc.get("season") != 2026:
        raise Step7ESmokeError("WNBA games/today did not return season 2026.")
    games = doc.get("games")
    if games is not None and not isinstance(games, list):
        raise Step7ESmokeError("WNBA games/today games field is not a list.")


ENDPOINTS: tuple[tuple[str, str, Callable[[Any], None]], ...] = (
    ("health", "/health", validate_health),
    ("root", "/", validate_root),
    ("openapi", "/openapi.json", validate_openapi),
    ("wnba_teams", "/api/v1/wnba/teams?season=2026", validate_teams),
    ("wnba_league", "/api/v1/wnba/league?season=2026", validate_league),
    ("step6r_supabase", "/api/v1/wnba/runtime/step6r-supabase-storage", validate_step6r),
    ("step6t_evidence_status", "/api/v1/wnba/runtime/step6t-canary-evidence/status", validate_step6t),
    ("step6u_bridge_status", "/api/v1/wnba/runtime/step6u-activation-bridge/status", validate_step6u),
    ("step6w_final_certificate", "/api/v1/wnba/runtime/step6w-final-certification", validate_step6w),
    ("wnba_games_today", "/api/v1/wnba/games/today?season=2026", validate_games_today),
)


def run_production_smoke() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=25.0, follow_redirects=True, headers={"user-agent": "kyre-sports-api-step7e-smoke/1"}) as client:
        for name, path, validator in ENDPOINTS:
            status, body, attempts, elapsed = _get_json(client, path)
            validator(body)
            results.append({
                "name": name,
                "path": path.split("?", 1)[0],
                "status_code": status,
                "attempts": attempts,
                "elapsed_seconds": elapsed,
                "passed": True,
                "summary": _safe_summary(body),
                "response_sha256": _sha256_json(body),
            })

    payload = {
        "model_version": MODEL_VERSION,
        "base_url": BASE_URL,
        "expected_release_revision": EXPECTED_RELEASE_REVISION,
        "endpoint_results": results,
        "safety": {
            "http_methods_used": ["GET"],
            "render_mutation_performed": False,
            "supabase_write_performed": False,
            "sportsbook_write_performed": False,
            "scheduler_authorized": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "secret_required": False,
            "secret_value_returned": False,
        },
    }
    manifest = _sha256_json(payload)
    return {
        "source": "Kyre Sports API WNBA Step 7E production smoke test",
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now(),
        "state": "wnba_production_smoke_passed",
        "smoke_complete": True,
        "base_url": BASE_URL,
        "expected_release_revision": EXPECTED_RELEASE_REVISION,
        "checks_total": len(results),
        "checks_passed": len(results),
        "checks_failed": 0,
        "endpoint_results": results,
        "smoke_manifest_sha256": manifest,
        "safety": payload["safety"],
    }


def main() -> int:
    print(json.dumps(run_production_smoke(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
