"""Reusable user-visible acceptance contracts for browser certification.

Monster Speed V3 Step 4 makes visible user behavior the blocking truth.
Telemetry remains evidence-only unless a contract explicitly marks it REQUIRED.
The module intentionally avoids importing Playwright so pure contract tests stay
dependency-light and callers can pass Playwright page/frame objects by duck type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

RESPONSIVE_VIEWPORTS = ((390, 844), (768, 1024), (1440, 1000))
QUERY_POLICY_TELEMETRY = "telemetry"
QUERY_POLICY_REQUIRED = "required"


class UserVisibleContractFailure(AssertionError):
    pass


@dataclass(frozen=True)
class UserVisibleContract:
    name: str
    required_selectors: tuple[str, ...]
    required_text: tuple[str, ...]
    required_markets: tuple[str, ...] = ()
    required_viewports: tuple[tuple[int, int], ...] = RESPONSIVE_VIEWPORTS
    query_policy: str = QUERY_POLICY_TELEMETRY
    required_query: tuple[tuple[str, str], ...] = ()
    overflow_tolerance_px: int = 2
    exact_selector_count: bool = True


def _last_query_value(query: Mapping[str, Any], key: str) -> str:
    raw = query.get(key, "")
    if isinstance(raw, (list, tuple)):
        return str(raw[-1]) if raw else ""
    return str(raw)


def evaluate_user_visible_evidence(
    contract: UserVisibleContract,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []

    selector_counts = dict(evidence.get("selector_counts") or {})
    selector_visible = dict(evidence.get("selector_visible") or {})
    for selector in contract.required_selectors:
        count = int(selector_counts.get(selector, 0))
        visible = bool(selector_visible.get(selector, False))
        if contract.exact_selector_count and count != 1:
            failures.append(f"selector_count:{selector}:{count}")
        elif count < 1:
            failures.append(f"selector_missing:{selector}")
        if not visible:
            failures.append(f"selector_not_visible:{selector}")

    body_text = str(evidence.get("body_text") or "")
    missing_text = [value for value in contract.required_text if value not in body_text]
    if missing_text:
        failures.append("missing_text:" + "|".join(missing_text))

    observed_markets = [str(x) for x in (evidence.get("observed_markets") or [])]
    for market in contract.required_markets:
        count = observed_markets.count(market)
        if count != 1:
            failures.append(f"market_count:{market}:{count}")

    dims = dict(evidence.get("dimensions") or {})
    body_scroll = int(dims.get("bodyScroll") or 0)
    doc_scroll = int(dims.get("docScroll") or 0)
    viewport = int(dims.get("viewport") or 0)
    if viewport <= 0:
        failures.append("viewport_missing")
    else:
        limit = viewport + int(contract.overflow_tolerance_px)
        if body_scroll > limit or doc_scroll > limit:
            failures.append(
                f"horizontal_overflow:body={body_scroll};doc={doc_scroll};viewport={viewport}"
            )

    query = dict(evidence.get("query") or {})
    query_matches = {
        key: _last_query_value(query, key) == expected
        for key, expected in contract.required_query
    }
    if contract.query_policy == QUERY_POLICY_REQUIRED:
        for key, matched in query_matches.items():
            if not matched:
                failures.append(
                    f"required_query:{key}:{_last_query_value(query, key)!r}"
                )
    elif contract.query_policy != QUERY_POLICY_TELEMETRY:
        failures.append(f"unknown_query_policy:{contract.query_policy}")

    if failures:
        raise UserVisibleContractFailure(
            f"{contract.name} user-visible contract failed: " + " | ".join(failures)
        )

    return {
        "status": "GREEN",
        "contract": contract.name,
        "required_selectors": list(contract.required_selectors),
        "required_text": list(contract.required_text),
        "required_markets": list(contract.required_markets),
        "observed_markets": observed_markets,
        "dimensions": dims,
        "query_policy": contract.query_policy,
        "query_matches": query_matches,
        "query": query,
        "url": str(evidence.get("url") or ""),
        "width": int(evidence.get("width") or viewport),
        "height": int(evidence.get("height") or 0),
    }


def certify_playwright_surface(
    *,
    page: Any,
    frame: Any,
    contract: UserVisibleContract,
    observed_markets: Sequence[str] = (),
    query: Mapping[str, Any] | None = None,
    timeout_ms: int = 45_000,
) -> dict[str, Any]:
    selector_counts: dict[str, int] = {}
    selector_visible: dict[str, bool] = {}
    for selector in contract.required_selectors:
        locator = frame.locator(selector)
        count = locator.count()
        selector_counts[selector] = count
        visible = False
        if count:
            locator.first.wait_for(state="visible", timeout=timeout_ms)
            visible = locator.first.is_visible()
        selector_visible[selector] = visible

    body = frame.locator("body")
    body_text = body.inner_text(timeout=5000)
    dims = body.evaluate(
        """e => ({
          bodyScroll:e.scrollWidth,
          docScroll:document.documentElement.scrollWidth,
          viewport:window.innerWidth
        })"""
    )
    viewport_size = page.viewport_size or {}
    evidence = {
        "selector_counts": selector_counts,
        "selector_visible": selector_visible,
        "body_text": body_text,
        "observed_markets": list(observed_markets),
        "dimensions": dims,
        "query": dict(query or {}),
        "url": page.url,
        "width": int(viewport_size.get("width") or dims.get("viewport") or 0),
        "height": int(viewport_size.get("height") or 0),
    }
    return evaluate_user_visible_evidence(contract, evidence)


def certify_responsive_suite(
    contract: UserVisibleContract,
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    observed = {
        (int(item.get("width") or 0), int(item.get("height") or 0))
        for item in results
        if item.get("status") == "GREEN"
    }
    expected = set(contract.required_viewports)
    missing = sorted(expected - observed)
    if missing:
        raise UserVisibleContractFailure(
            f"{contract.name} responsive proof missing viewports: {missing!r}"
        )
    return {
        "status": "GREEN",
        "contract": contract.name,
        "required_viewports": [list(x) for x in contract.required_viewports],
        "observed_viewports": [list(x) for x in sorted(observed)],
        "user_behavior_blocking": True,
        "telemetry_blocking": contract.query_policy == QUERY_POLICY_REQUIRED,
    }
