"""OFF-only probe of the real Step 7G FastAPI release defaults.

Unlike earlier boundary-isolation probes, this diagnostic intentionally sends no
query overrides to the public model-input-readiness route. The route's own
frozen defaults therefore remain authoritative: current availability, shot
context, advanced context, and officiating context are all requested.

The probe selects a real upcoming WNBA game and a recently active player, calls
the actual FastAPI endpoint, and records only sanitized evidence. It never
enables production runtime, schedulers, sportsbook sync, persistence, or
Supabase mutation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

REPORT_PATH = Path("step7g-fastapi-release-defaults-probe.json")
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_safe() -> None:
    bad = {key: os.getenv(key) for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))}
    if bad:
        raise RuntimeError(
            "Step 7G release-default probe refuses to run while a production switch is enabled: "
            + ", ".join(sorted(bad))
        )
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Step 7G release-default probe requires first-party mode ON in CI.")


def _exception_chain(exc: BaseException, *, max_depth: int = 8) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and len(rows) < max_depth and id(current) not in seen:
        seen.add(id(current))
        rows.append(
            {
                "type": type(current).__name__,
                "module": type(current).__module__,
                "message": str(current)[:1400],
            }
        )
        if current.__cause__ is not None:
            current = current.__cause__
        elif current.__context__ is not None and not current.__suppress_context__:
            current = current.__context__
        else:
            current = None
    return rows


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)

    from sports_api.main import app
    import sports_api.wnba_step7g_first_party_integration as integration
    from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector

    status = integration.get_step7g_first_party_status()
    if not status.get("all_core_seams_installed"):
        raise RuntimeError("Step 7G first-party integration was not installed before router binding.")
    if not status.get("certified_scope", {}).get("current_availability"):
        raise RuntimeError("Step 4I current availability is not formally certified in the integration contract.")

    selector.MIN_TIP_BUFFER_HOURS = 0.5
    selected_game, selected_player, _ = selector._select_live_pregame_case()
    game_id = str(selected_game["game_id"])
    player_id = int(selected_player["player_id"])
    path = f"/api/v1/wnba/games/{game_id}/players/{player_id}/model-input-readiness"

    # Intentionally empty: exercise the public route's real defaults exactly.
    params: dict[str, Any] = {}

    response = None
    body: Any = None
    exception_rows: list[dict[str, str]] = []
    with TestClient(app, raise_server_exceptions=True) as client:
        try:
            response = client.get(path)
        except Exception as exc:
            exception_rows = _exception_chain(exc)

    if exception_rows:
        outcome = "RELEASE_DEFAULT_EXCEPTION_BOUNDARY_CAPTURED"
        http_status = None
        readiness = None
        can_start = None
        summary = None
        next_dependency = "See sanitized exception_chain for first unresolved default-route dependency"
    else:
        assert response is not None
        http_status = response.status_code
        try:
            body = response.json()
        except Exception:
            body = {"raw_body_prefix": response.text[:1000]}
        summary = body.get("summary") if isinstance(body, dict) else None
        readiness = body.get("readiness") if isinstance(body, dict) else None
        can_start = body.get("can_start_projection") if isinstance(body, dict) else None
        if response.status_code == 200:
            outcome = "RELEASE_DEFAULT_PATH_RETURNED"
            next_dependency = None
        elif response.status_code == 502:
            outcome = "RELEASE_DEFAULT_UPSTREAM_BOUNDARY_CAPTURED"
            next_dependency = "Default-route upstream dependency"
        elif response.status_code == 404:
            outcome = "RELEASE_DEFAULT_NOT_FOUND_BOUNDARY_CAPTURED"
            next_dependency = "Default-route data discovery dependency"
        else:
            outcome = "UNEXPECTED_RELEASE_DEFAULT_RESPONSE"
            next_dependency = "Investigate unexpected default-route response"

    report = {
        "data_type": "wnba_step7g_fastapi_release_defaults_probe_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": path,
        "request_params": params,
        "route_defaults_exercised": {
            "season": "router default",
            "season_type": "router default",
            "last_n_games": "router default",
            "require_current_availability": True,
            "include_shot_context": True,
            "include_advanced_context": True,
            "include_officiating_context": True,
            "include_snapshot": False,
        },
        "selected_game": selected_game,
        "selected_player": selected_player,
        "http_status": http_status,
        "probe_outcome": outcome,
        "next_required_dependency": next_dependency,
        "readiness": readiness,
        "can_start_projection": can_start,
        "summary": summary,
        "response_body": body,
        "exception_chain": exception_rows,
        "integration_status": status,
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
            "step7g_first_party_enabled_for_ci_process_only": True,
            "traceback_frames_persisted": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()

    if outcome == "UNEXPECTED_RELEASE_DEFAULT_RESPONSE":
        raise RuntimeError(f"Unexpected release-default HTTP {http_status}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
