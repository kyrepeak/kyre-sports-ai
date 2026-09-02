"""Exhaustive read-only follow-up for Step 7G exact WNBA rotations.

Closes two discovery gaps left by the first rotation-surface probe:
1) scan every WNBA.com JavaScript asset discovered from the relevant pages and
   build manifests (rather than stopping at the initial safety cap);
2) safely GET a small, explicit family of plausible same-origin rotation API and
   page routes and record only status/schema evidence.

No rotation is reconstructed from play-by-play and no production state is read
or mutated beyond verifying that activation flags are OFF.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from sports_api.tools.wnba_step7g_rotation_surface_probe import (
    BASE_URL,
    DISCOVERY_MARKERS,
    EXACT_MARKERS,
    GAME_ID,
    HEADERS,
    MAX_ASSET_BYTES,
    OFF_ENV,
    PLAYER_ID,
    _api_candidates,
    _manifest_script_paths,
    _marker_hits,
    _next_data,
    _script_paths,
    _walk_key_hits,
)

REPORT_PATH = Path("step7g-rotation-exhaustive-probe.json")

API_PATHS = (
    "/api/stats/gamerotation",
    "/api/stats/game-rotation",
    "/api/stats/rotation",
    "/api/gamerotation",
    "/api/game-rotation",
    "/api/rotation",
)
API_PARAM_VARIANTS = ("gameId", "GameID", "gameID", "game_id")
PAGE_PATHS = (
    f"/game/{GAME_ID}/rotation",
    f"/game/{GAME_ID}/rotations",
    f"/game/{GAME_ID}/lineups",
    f"/game/{GAME_ID}/on-court",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_shape(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"type": "object", "top_level_keys": sorted(str(key) for key in value)[:100]}
    if isinstance(value, list):
        return {"type": "array", "length": len(value)}
    return {"type": type(value).__name__}


def _summarize_response(response: httpx.Response) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status_code": response.status_code,
        "url": str(response.url),
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
    }
    if not response.content:
        return result
    try:
        parsed = response.json()
    except ValueError:
        text = response.text
        result["body_kind"] = "text_or_html"
        result["marker_hits"] = _marker_hits(text)
        return result
    result["body_kind"] = "json"
    result["json_shape"] = _json_shape(parsed)
    compact = json.dumps(parsed, separators=(",", ":"), default=str)
    result["marker_hits"] = _marker_hits(compact)
    return result


def main() -> None:
    off_state = {key: os.getenv(key, "").strip().casefold() == "false" for key in OFF_ENV}
    if not all(off_state.values()):
        raise RuntimeError("Exhaustive rotation probe refused because a production flag is not OFF.")

    page_urls = (
        f"{BASE_URL}/game/{GAME_ID}",
        f"{BASE_URL}/game/{GAME_ID}/box-score",
        f"{BASE_URL}/game/{GAME_ID}/play-by-play",
        f"{BASE_URL}/player/{PLAYER_ID}",
    )

    asset_paths: set[str] = set()
    build_ids: set[str] = set()
    source_pages: list[dict[str, Any]] = []

    with httpx.Client(headers=HEADERS, timeout=12.0, follow_redirects=True) as client:
        for url in page_urls:
            response = client.get(url)
            response.raise_for_status()
            payload = _next_data(response.text)
            build_id = payload.get("buildId")
            if isinstance(build_id, str) and build_id:
                build_ids.add(build_id)
            scripts = _script_paths(response.text)
            asset_paths.update(scripts)
            source_pages.append({
                "url": str(response.url),
                "status_code": response.status_code,
                "build_id": build_id,
                "script_count": len(scripts),
            })

        manifests: list[dict[str, Any]] = []
        for build_id in sorted(build_ids):
            for suffix in ("_buildManifest.js", "_ssgManifest.js"):
                url = f"{BASE_URL}/_next/static/{build_id}/{suffix}"
                response = client.get(url)
                text = response.text if response.status_code == 200 else ""
                discovered = _manifest_script_paths(text)
                asset_paths.update(discovered)
                manifests.append({
                    "url": url,
                    "status_code": response.status_code,
                    "bytes": len(response.content),
                    "discovered_script_count": len(discovered),
                })

        normalized_assets: set[str] = set()
        for value in asset_paths:
            absolute = urljoin(BASE_URL + "/", value)
            parsed = urlparse(absolute)
            if parsed.hostname == "www.wnba.com" and parsed.path.endswith(".js"):
                normalized_assets.add(absolute)

        aggregate: Counter[str] = Counter()
        assets_with_relevant_hits: list[dict[str, Any]] = []
        literal_api_candidates: set[str] = set()
        scanned = 0
        skipped_oversize = 0
        failed_assets: list[dict[str, Any]] = []

        for url in sorted(normalized_assets):
            try:
                response = client.get(url)
                if response.status_code != 200:
                    failed_assets.append({"url": url, "status_code": response.status_code})
                    continue
                scanned += 1
                if len(response.content) > MAX_ASSET_BYTES:
                    skipped_oversize += 1
                    continue
                text = response.text
                hits = _marker_hits(text)
                api_candidates = _api_candidates(text)
                literal_api_candidates.update(api_candidates)
                for marker, data in hits.items():
                    aggregate[marker] += int(data["count"])
                meaningful = {
                    marker: data for marker, data in hits.items()
                    if marker in EXACT_MARKERS
                    or marker in ("getGameRotation", "onCourt", "on_court", "lineup")
                    or marker == "/api/"
                }
                rotation_api_literals = sorted(
                    candidate for candidate in api_candidates
                    if "rotation" in candidate.casefold()
                    or "lineup" in candidate.casefold()
                    or "stint" in candidate.casefold()
                )
                if meaningful or rotation_api_literals:
                    assets_with_relevant_hits.append({
                        "url": url,
                        "bytes": len(response.content),
                        "marker_hits": meaningful,
                        "rotation_api_literals": rotation_api_literals,
                    })
            except httpx.HTTPError as exc:
                failed_assets.append({"url": url, "error": type(exc).__name__})

        # Probe only a tightly bounded same-origin route family. A 400/422 means
        # a route may exist but reject our first parameter spelling, so only then
        # try the other known GameID spellings.
        api_route_results: list[dict[str, Any]] = []
        for path in API_PATHS:
            first = client.get(urljoin(BASE_URL, path), params={"gameId": GAME_ID})
            entry: dict[str, Any] = {
                "path": path,
                "attempts": [{"parameter": "gameId", **_summarize_response(first)}],
            }
            if first.status_code in (400, 405, 422):
                for parameter in API_PARAM_VARIANTS[1:]:
                    response = client.get(urljoin(BASE_URL, path), params={parameter: GAME_ID})
                    entry["attempts"].append({
                        "parameter": parameter,
                        **_summarize_response(response),
                    })
                    if response.status_code == 200:
                        break
            api_route_results.append(entry)

        hidden_page_results: list[dict[str, Any]] = []
        for path in PAGE_PATHS:
            response = client.get(urljoin(BASE_URL, path))
            entry = _summarize_response(response)
            entry["path"] = path
            if response.status_code == 200 and "text/html" in response.headers.get("content-type", ""):
                try:
                    payload = _next_data(response.text)
                    props = payload.get("props")
                    page_props = props.get("pageProps") if isinstance(props, dict) else None
                    entry["next_page"] = payload.get("page")
                    entry["build_id"] = payload.get("buildId")
                    entry["page_props_top_level_keys"] = (
                        sorted(page_props) if isinstance(page_props, dict) else []
                    )
                    entry["rotationish_key_hits"] = (
                        _walk_key_hits(page_props) if isinstance(page_props, dict) else []
                    )
                except Exception as exc:
                    entry["next_data_error"] = type(exc).__name__
            hidden_page_results.append(entry)

    exact_totals = {marker: aggregate.get(marker, 0) for marker in EXACT_MARKERS}
    exact_bundle = all(
        exact_totals.get(marker, 0) > 0
        for marker in ("IN_TIME_REAL", "OUT_TIME_REAL", "PLAYER_PTS", "PT_DIFF", "USG_PCT")
    )
    rotation_literals = sorted(
        candidate for candidate in literal_api_candidates
        if any(token in candidate.casefold() for token in ("rotation", "lineup", "stint"))
    )
    successful_api_candidates = [
        attempt
        for route in api_route_results
        for attempt in route["attempts"]
        if attempt["status_code"] == 200
        and attempt.get("body_kind") == "json"
        and any(marker in attempt.get("marker_hits", {}) for marker in EXACT_MARKERS)
    ]
    successful_hidden_pages = [
        page for page in hidden_page_results
        if page.get("status_code") == 200
        and page.get("next_page") not in ("/_error", "/404")
        and page.get("rotationish_key_hits")
    ]

    report = {
        "data_type": "wnba_step7g_exact_rotation_exhaustive_probe",
        "created_at_utc": _now(),
        "read_only": True,
        "target_game_id": GAME_ID,
        "target_player_id": PLAYER_ID,
        "production_flags_off": off_state,
        "source_pages": source_pages,
        "build_ids": sorted(build_ids),
        "manifests": manifests,
        "javascript_scan": {
            "assets_discovered": len(normalized_assets),
            "assets_scanned_successfully": scanned,
            "assets_skipped_oversize": skipped_oversize,
            "failed_asset_count": len(failed_assets),
            "failed_assets": failed_assets,
            "aggregate_marker_counts": dict(sorted(aggregate.items())),
            "exact_marker_totals": exact_totals,
            "exact_contract_field_bundle_found": exact_bundle,
            "literal_api_candidate_count": len(literal_api_candidates),
            "rotation_lineup_stint_api_literals": rotation_literals,
            "assets_with_relevant_hits": assets_with_relevant_hits,
        },
        "same_origin_api_route_probe": api_route_results,
        "hidden_game_page_probe": hidden_page_results,
        "decision": {
            "exact_rotation_source_certified": False,
            "all_discovered_assets_scanned": scanned + skipped_oversize + len(failed_assets) == len(normalized_assets),
            "exact_contract_field_bundle_found": exact_bundle,
            "rotation_api_literal_found": bool(rotation_literals),
            "rotation_api_response_with_exact_markers_found": bool(successful_api_candidates),
            "hidden_rotation_page_with_rotationish_payload_found": bool(successful_hidden_pages),
            "pbp_reconstruction_attempted": False,
            "production_activation_allowed": False,
        },
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "frozen_shared_provider_behavior_changed": False,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "assets_discovered": len(normalized_assets),
        "assets_scanned_successfully": scanned,
        "exact_contract_field_bundle_found": exact_bundle,
        "rotation_api_literal_count": len(rotation_literals),
        "rotation_api_exact_response_count": len(successful_api_candidates),
        "hidden_rotation_page_count": len(successful_hidden_pages),
        "production_activation_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
