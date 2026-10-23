"""Exact-candidate live-route proof for the NFL Rushing Yards timeout repair.

This verifier intentionally exercises the FastAPI application route used by the
Vercel entrypoint.  The 15-second deadline includes a cold import of the API
entrypoint plus the full /slate request so the proof cannot accidentally certify
a lightweight /status path.
"""
from __future__ import annotations

import importlib
import json
import signal
import time
from typing import Any

from fastapi.testclient import TestClient

ROUTE = "/api/v1/nfl/rushing-yards/slate"
MAX_SECONDS = 15.0


class FullSlateDeadlineExceeded(RuntimeError):
    pass


def _deadline_handler(_signum: int, _frame: Any) -> None:
    raise FullSlateDeadlineExceeded("NFL_RUSHING_FULL_SLATE_EXCEEDED_15_SECONDS")


def _require_payload_contract(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("NFL_RUSHING_FULL_SLATE_PAYLOAD_NOT_OBJECT")
    routing = payload.get("routing")
    if not isinstance(routing, dict):
        raise RuntimeError("NFL_RUSHING_FULL_SLATE_ROUTING_MISSING")
    policy = routing.get("request_time_transport_policy")
    if not isinstance(policy, dict):
        raise RuntimeError("NFL_RUSHING_FULL_SLATE_FASTPATH_POLICY_MISSING")
    if policy.get("full_pbp_downloads") is not False:
        raise RuntimeError("NFL_RUSHING_FULL_SLATE_PBP_FASTPATH_NOT_ACTIVE")
    if policy.get("current_stats_roster_history_prewarm") != "CONCURRENT":
        raise RuntimeError("NFL_RUSHING_FULL_SLATE_PREWARM_NOT_CONCURRENT")
    if policy.get("slow_enrichment_blocks_slate") is not False:
        raise RuntimeError("NFL_RUSHING_FULL_SLATE_ENRICHMENT_NOT_BOUNDED")
    return payload


def main() -> int:
    if not hasattr(signal, "setitimer"):
        raise RuntimeError("NFL_RUSHING_FULL_SLATE_DEADLINE_SIGNAL_UNAVAILABLE")

    started = time.monotonic()
    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _deadline_handler)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    response = None
    try:
        entrypoint = importlib.import_module("kyre_sports_api_vercel_v1")
        with TestClient(entrypoint.app) as client:
            response = client.get(ROUTE)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous)

    elapsed = time.monotonic() - started
    if elapsed >= MAX_SECONDS:
        raise FullSlateDeadlineExceeded(
            f"NFL_RUSHING_FULL_SLATE_EXCEEDED_15_SECONDS:{elapsed:.3f}"
        )
    if response is None:
        raise RuntimeError("NFL_RUSHING_FULL_SLATE_RESPONSE_MISSING")
    if response.status_code != 200:
        raise RuntimeError(
            f"NFL_RUSHING_FULL_SLATE_HTTP_{response.status_code}:{response.text[:300]}"
        )

    payload = _require_payload_contract(response.json())
    games = payload.get("games")
    result = {
        "proof": "API2_NFL_RUSHING_LIVE_TIMEOUT_V1",
        "route": ROUTE,
        "status_code": response.status_code,
        "elapsed_seconds": round(elapsed, 3),
        "ceiling_seconds": MAX_SECONDS,
        "full_pbp_downloads": False,
        "prewarm": "CONCURRENT",
        "slow_enrichment_blocks_slate": False,
        "game_count": len(games) if isinstance(games, list) else None,
        "ok": True,
    }
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
