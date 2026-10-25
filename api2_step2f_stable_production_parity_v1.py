"""API 2 Step 2F stable-production parity gate.

Step 2E answers "which canonical runtime owns this page?". Step 2F answers the
separate production question: "is the stable service actually serving the exact
frozen build, and is every visible sports page represented by that stable
production surface?"

The gate is deliberately registry-driven. It derives the page surface from the
universal navigation registry, reuses Step 2E ownership for NFL/CFB/NBA/WNBA,
and preserves MLB's existing stable Render service boundary.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.request import Request, urlopen

from api2_universal_sports_router_registry_v1 import (
    ROUTER_REGISTRY,
    validate_router_registry,
)
from universal_sports_nav_registry_v1 import validate_registry as validate_nav_registry
from universal_sports_nav_registry_v1 import visible_sports


MODEL_VERSION = "API2_STEP2F_STABLE_PRODUCTION_PARITY_V1"
API2_STEP2F_STABLE_PRODUCTION_PARITY_V1_FROZEN = True
STABLE_VERCEL_ALIAS = "https://kyre-sports-api.vercel.app"
MLB_STABLE_SERVICE = "https://kyre-sports-api.onrender.com"
EXPECTED_VERCEL_HOST = "kyre-sports-api.vercel.app"
EXPECTED_GIT_REF = "api2-main"
EXPECTED_PAGE_COUNT = 39
STEP2E_SCOPE = frozenset({"nfl", "cfb", "nba", "wnba"})
MLB_SCOPE = frozenset({"mlb"})


def visible_page_keys() -> tuple[tuple[str, str], ...]:
    return tuple(
        (sport.id, market.id)
        for sport in visible_sports()
        for market in sport.markets
        if market.live
    )


def _host(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("https://"):
        text = text[8:]
    elif text.startswith("http://"):
        text = text[7:]
    return text.rstrip("/")


def build_page_receipts() -> tuple[dict[str, Any], ...]:
    receipts: list[dict[str, Any]] = []
    for sport_id, market_id in visible_page_keys():
        registration = ROUTER_REGISTRY.get((sport_id, market_id))
        if sport_id in STEP2E_SCOPE:
            receipts.append(
                {
                    "sport": sport_id,
                    "market": market_id,
                    "page_key": f"{sport_id}/{market_id}",
                    "stable_service": STABLE_VERCEL_ALIAS,
                    "proof_mode": "vercel-stable-alias+step2e+live-coverage",
                    "step2e_owned": registration is not None,
                    "canonical_adapter": registration.adapter_kind if registration else None,
                    "canonical_target": registration.target if registration else None,
                }
            )
        else:
            receipts.append(
                {
                    "sport": sport_id,
                    "market": market_id,
                    "page_key": f"{sport_id}/{market_id}",
                    "stable_service": MLB_STABLE_SERVICE,
                    "proof_mode": "render-stable-service+nav-owner",
                    "step2e_owned": False,
                    "canonical_adapter": "mlb-existing-stable-runtime",
                    "canonical_target": "kyre-sports-api.onrender.com",
                }
            )
    return tuple(receipts)


def validate_static_contract() -> tuple[str, ...]:
    errors: list[str] = []
    errors.extend(f"nav: {item}" for item in validate_nav_registry())
    errors.extend(f"step2e: {item}" for item in validate_router_registry())

    keys = visible_page_keys()
    if len(keys) != EXPECTED_PAGE_COUNT:
        errors.append(f"page-count: expected {EXPECTED_PAGE_COUNT}, got {len(keys)}")
    if len(keys) != len(set(keys)):
        errors.append("page-surface: duplicate visible page keys")

    receipts = build_page_receipts()
    if len(receipts) != EXPECTED_PAGE_COUNT:
        errors.append("receipt-surface: incomplete page receipt matrix")

    for item in receipts:
        key = (item["sport"], item["market"])
        if item["sport"] in STEP2E_SCOPE:
            if key not in ROUTER_REGISTRY:
                errors.append(f"{item['page_key']}: missing Step 2E owner")
            if item["stable_service"] != STABLE_VERCEL_ALIAS:
                errors.append(f"{item['page_key']}: wrong stable Vercel service")
        elif item["sport"] == "mlb":
            if item["stable_service"] != MLB_STABLE_SERVICE:
                errors.append(f"{item['page_key']}: wrong MLB stable service")
        else:
            errors.append(f"{item['page_key']}: no Step 2F service owner")

    return tuple(errors)


def evaluate_vercel_receipt(
    receipt: Mapping[str, Any], *, expected_sha: str
) -> tuple[str, ...]:
    errors: list[str] = []
    expected_sha = str(expected_sha or "").strip().lower()
    actual_sha = str(receipt.get("git_commit_sha") or "").strip().lower()
    env = str(receipt.get("environment") or "").strip().lower()
    target_env = str(receipt.get("target_environment") or "").strip().lower()
    ref = str(receipt.get("git_commit_ref") or "").strip()
    production_url = _host(receipt.get("production_url"))

    if len(expected_sha) != 40:
        errors.append("expected SHA must be a full 40-character commit SHA")
    if env != "production":
        errors.append(f"stable alias is not a production deployment: VERCEL_ENV={env or 'missing'}")
    if target_env != "production":
        errors.append(
            f"stable alias target environment is not production: VERCEL_TARGET_ENV={target_env or 'missing'}"
        )
    if actual_sha != expected_sha:
        errors.append(f"stable production SHA mismatch: expected {expected_sha}, got {actual_sha or 'missing'}")
    if ref != EXPECTED_GIT_REF:
        errors.append(f"stable production Git ref mismatch: expected {EXPECTED_GIT_REF}, got {ref or 'missing'}")
    if production_url != EXPECTED_VERCEL_HOST:
        errors.append(
            f"stable production alias mismatch: expected {EXPECTED_VERCEL_HOST}, got {production_url or 'missing'}"
        )
    return tuple(errors)


def _fetch_json(url: str, *, timeout: float = 25.0) -> tuple[int, dict[str, Any]]:
    request = Request(url, headers={"User-Agent": "api2-step2f-stable-production-parity-v1"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed HTTPS production hosts only
        raw = response.read()
        status = int(getattr(response, "status", 200))
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Step 2F expected object JSON from {url}")
    return status, payload


def _live_page_matrix(
    *, coverage: Mapping[str, Any], render_healthy: bool
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    failures: list[str] = []
    output: list[dict[str, Any]] = []
    coverage_by_sport = coverage.get("coverage") if isinstance(coverage.get("coverage"), dict) else {}

    for static in build_page_receipts():
        item = dict(static)
        if item["sport"] == "mlb":
            item["live_verified"] = bool(render_healthy)
            item["live_owner"] = MLB_STABLE_SERVICE
            if not render_healthy:
                failures.append(f"{item['page_key']}: MLB stable service unhealthy")
        else:
            sport_cov = coverage_by_sport.get(item["sport"], {}) if isinstance(coverage_by_sport, dict) else {}
            market_cov = sport_cov.get(item["market"], {}) if isinstance(sport_cov, dict) else {}
            live_ok = bool(
                isinstance(market_cov, dict)
                and market_cov.get("mounted") is True
                and market_cov.get("application_gateway") == "KYRE_SPORTS_API"
                and market_cov.get("provider_direct_frontend") is False
            )
            item["live_verified"] = live_ok
            item["live_owner"] = market_cov.get("owner_kind") if isinstance(market_cov, dict) else None
            item["canonical_path"] = market_cov.get("canonical_path") if isinstance(market_cov, dict) else None
            if not live_ok:
                failures.append(f"{item['page_key']}: stable Kyre Sports API coverage missing/unhealthy")
        output.append(item)

    return tuple(output), tuple(failures)


def verify_live_production(*, expected_sha: str) -> dict[str, Any]:
    failures: list[str] = list(validate_static_contract())

    receipt_status, deployment_receipt = _fetch_json(
        STABLE_VERCEL_ALIAS + "/api/v1/system/deployment-receipt"
    )
    if receipt_status != 200:
        failures.append(f"deployment-receipt HTTP {receipt_status}")
    failures.extend(evaluate_vercel_receipt(deployment_receipt, expected_sha=expected_sha))

    health_status, health = _fetch_json(STABLE_VERCEL_ALIAS + "/health")
    if health_status != 200 or health.get("status") != "healthy":
        failures.append(f"Kyre Sports API stable health failed: HTTP {health_status} status={health.get('status')}")

    coverage_status, coverage = _fetch_json(STABLE_VERCEL_ALIAS + "/api/v1/router/coverage")
    if coverage_status != 200 or coverage.get("status") != "GREEN" or coverage.get("failures") not in ([], ()):
        failures.append("Kyre Sports API stable router coverage is not GREEN/empty-failures")

    render_healthy = False
    render_detail: dict[str, Any] = {}
    try:
        render_status, render_detail = _fetch_json(MLB_STABLE_SERVICE + "/health", timeout=30.0)
        render_state = str(render_detail.get("status") or "").strip().lower()
        render_healthy = render_status == 200 and render_state in {"healthy", "ok", "ready", "green"}
    except Exception as exc:  # fail closed with a public diagnostic only
        render_detail = {"status": "unavailable", "diagnostic": type(exc).__name__}
    if not render_healthy:
        failures.append("MLB stable Render service health is not GREEN")

    pages, page_failures = _live_page_matrix(coverage=coverage, render_healthy=render_healthy)
    failures.extend(page_failures)
    unique_failures = tuple(dict.fromkeys(failures))

    return {
        "schema_version": MODEL_VERSION,
        "status": "GREEN" if not unique_failures else "RED",
        "stable_vercel_alias": STABLE_VERCEL_ALIAS,
        "mlb_stable_service": MLB_STABLE_SERVICE,
        "expected_sha": expected_sha,
        "deployment_receipt": deployment_receipt,
        "kyre_health": health,
        "router_coverage_status": coverage.get("status"),
        "mlb_health_status": render_detail.get("status"),
        "page_count": len(pages),
        "verified_page_count": sum(1 for item in pages if item.get("live_verified")),
        "pages": list(pages),
        "failures": list(unique_failures),
        "preview_counts_as_production": False,
        "step2e_plus_step2f_required_for_freeze": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="API2 Step 2F stable-production parity gate")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--expected-sha", default="")
    parser.add_argument("--receipt-out", default="")
    args = parser.parse_args()

    if args.live:
        result = verify_live_production(expected_sha=args.expected_sha)
    else:
        failures = validate_static_contract()
        result = {
            "schema_version": MODEL_VERSION,
            "status": "GREEN" if not failures else "RED",
            "page_count": len(visible_page_keys()),
            "pages": list(build_page_receipts()),
            "failures": list(failures),
        }

    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.receipt_out:
        Path(args.receipt_out).write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["status"] == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
