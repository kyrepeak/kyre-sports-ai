"""WNBA PRA Maximum-Speed Snapshot V1 latency/evidence profiler.

This module does not optimize or mutate production behavior. It records the
observable first-paint contract and fails closed when the approved targets miss.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Callable, Mapping

PROFILE_VERSION = "WNBA_PRA_MAX_SPEED_PROFILE_V1"
TARGET_MS = {
    "warm": 500.0,
    "return": 500.0,
    "return_switch": 500.0,
    "normal_fresh": 1000.0,
    "cold_valid_artifact": 2000.0,
    "cold_streamlit_valid_artifact": 2000.0,
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def profile_snapshot(
    *,
    candidate_sha: str,
    load_class: str,
    fetch: Callable[[], Mapping[str, Any]],
    render: Callable[[Mapping[str, Any]], Any],
    perf_counter: Callable[[], float] = time.perf_counter,
    duplicate_refresh_count: int = 0,
) -> dict[str, Any]:
    """Measure one fetch + one render without introducing extra network reads."""
    sha = str(candidate_sha or "").strip().lower()
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise ValueError("WNBA_PRA_PROFILE_CANDIDATE_SHA_INVALID")
    klass = str(load_class or "").strip().lower()
    if klass not in TARGET_MS:
        raise ValueError("WNBA_PRA_PROFILE_LOAD_CLASS_INVALID")

    total_start = perf_counter()
    payload = dict(fetch())
    after_fetch = perf_counter()
    render(payload)
    after_render = perf_counter()
    total_end = perf_counter()

    return {
        "profile_version": PROFILE_VERSION,
        "candidate_sha": sha,
        "schema": str(payload.get("schema_version") or ""),
        "snapshot_state": str(payload.get("snapshot_state") or ""),
        "cache_state": str(payload.get("cache_state") or ""),
        "load_class": klass,
        "initial_network_reads": 1,
        "market_board_reads": int(payload.get("market_board_reads") or 0),
        "backend_ms": round(_number(payload.get("assembly_ms")), 3),
        "client_ms": round((after_fetch - total_start) * 1000.0, 3),
        "render_ms": round((after_render - after_fetch) * 1000.0, 3),
        "total_ms": round((total_end - total_start) * 1000.0, 3),
        "duplicate_refresh_count": int(duplicate_refresh_count),
        "refresh_required": bool(payload.get("refresh_required")),
        "selected_provider": payload.get("selected_provider"),
        "sportsbooks": list(payload.get("sportsbooks") or []),
        "market_capture_at": payload.get("market_capture_at"),
    }


def evaluate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Return a machine-readable fail-closed acceptance verdict."""
    klass = str(profile.get("load_class") or "").strip().lower()
    target = TARGET_MS.get(klass)
    failures: list[dict[str, Any]] = []

    if target is None:
        failures.append({"code": "UNKNOWN_LOAD_CLASS", "actual": klass, "target": sorted(TARGET_MS)})
    elif _number(profile.get("total_ms"), float("inf")) >= target:
        failures.append({"code": "TOTAL_LATENCY_TARGET_MISSED", "actual_ms": _number(profile.get("total_ms")), "target_lt_ms": target})

    if int(profile.get("initial_network_reads") or 0) != 1:
        failures.append({"code": "INITIAL_NETWORK_READS_NOT_ONE", "actual": int(profile.get("initial_network_reads") or 0), "target": 1})
    if int(profile.get("market_board_reads") or 0) != 1:
        failures.append({"code": "MARKET_BOARD_READS_NOT_ONE", "actual": int(profile.get("market_board_reads") or 0), "target": 1})
    if int(profile.get("duplicate_refresh_count") or 0) != 0:
        failures.append({"code": "DUPLICATE_REFRESH_DETECTED", "actual": int(profile.get("duplicate_refresh_count") or 0), "target": 0})

    return {
        "passed": not failures,
        "load_class": klass,
        "target_lt_ms": target,
        "failures": failures,
    }


def profile_certified_endpoint(*, candidate_sha: str, load_class: str, day: str, season: int = 2026) -> dict[str, Any]:
    """Profile the certified Kyre page-snapshot read without invoking player detail."""
    from wnba_pra_page_snapshot_client_v1 import fetch_page_snapshot

    evidence = profile_snapshot(
        candidate_sha=candidate_sha,
        load_class=load_class,
        fetch=lambda: fetch_page_snapshot(day, season=season),
        render=lambda _payload: None,
    )
    evidence["verdict"] = evaluate_profile(evidence)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", default=os.environ.get("VERCEL_GIT_COMMIT_SHA", ""))
    parser.add_argument("--load-class", required=True, choices=sorted(TARGET_MS))
    parser.add_argument("--date", required=True)
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args(argv)
    evidence = profile_certified_endpoint(
        candidate_sha=args.candidate_sha,
        load_class=args.load_class,
        day=args.date,
        season=args.season,
    )
    print(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    return 0 if evidence["verdict"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
