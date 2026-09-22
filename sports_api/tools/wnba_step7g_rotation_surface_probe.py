"""Deep read-only probe for an exact official WNBA rotation surface.

Step 7G already has first-party WNBA.com schedule, box-score, recent-history,
and play-by-play coverage. The remaining frozen Step 4R contract requires exact
source rotation stints containing IN_TIME_REAL / OUT_TIME_REAL plus PLAYER_PTS,
PT_DIFF and USG_PCT. This diagnostic searches the current server-rendered page
payloads and the JavaScript assets WNBA.com itself ships for evidence of such a
surface. It does not reconstruct rotations from substitutions and never writes
to production.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

BASE_URL = "https://www.wnba.com"
GAME_ID = "1022600288"
PLAYER_ID = 1629498
REPORT_PATH = Path("step7g-rotation-surface-probe.json")
MAX_ASSETS = 120
MAX_ASSET_BYTES = 6_000_000
CONTEXT_RADIUS = 120
MAX_CONTEXTS_PER_MARKER = 4

OFF_ENV = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)

EXACT_MARKERS = (
    "gamerotation",
    "gameRotation",
    "IN_TIME_REAL",
    "OUT_TIME_REAL",
    "PLAYER_PTS",
    "PT_DIFF",
    "USG_PCT",
)
DISCOVERY_MARKERS = EXACT_MARKERS + (
    "getGameRotation",
    "rotation",
    "onCourt",
    "on_court",
    "lineup",
    "substitution",
    "stats.nba.com",
    "stats.wnba.com",
    "/stats/",
    "/api/",
)
ROTATIONISH_KEY_PARTS = (
    "rotation",
    "court",
    "lineup",
    "stint",
    "sub",
    "in_time",
    "out_time",
    "player_pts",
    "pt_diff",
    "usg",
)

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
}


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        data = {str(key): value for key, value in attrs}
        if data.get("id") == "__NEXT_DATA__":
            self.capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self.capture:
            self.capture = False

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)

    @property
    def text(self) -> str:
        return "".join(self.parts).strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_data(html: str) -> dict[str, Any]:
    parser = _NextDataParser()
    parser.feed(html)
    if not parser.text:
        raise RuntimeError("WNBA page did not expose __NEXT_DATA__.")
    payload = json.loads(parser.text)
    if not isinstance(payload, dict):
        raise RuntimeError("WNBA __NEXT_DATA__ was not an object.")
    return payload


def _rotationish_key(key: Any) -> bool:
    lowered = str(key).casefold()
    return any(part in lowered for part in ROTATIONISH_KEY_PARTS)


def _walk_key_hits(value: Any, path: str = "$", *, limit: int = 300) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []

    def walk(node: Any, here: str) -> None:
        if len(hits) >= limit:
            return
        if isinstance(node, dict):
            for key, child in node.items():
                child_path = f"{here}.{key}"
                if _rotationish_key(key):
                    hits.append({"path": child_path, "value_type": type(child).__name__})
                    if len(hits) >= limit:
                        return
                walk(child, child_path)
        elif isinstance(node, list):
            for index, child in enumerate(node[:1000]):
                walk(child, f"{here}[{index}]")
                if len(hits) >= limit:
                    return

    walk(value, path)
    return hits


def _find_action_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        direct = [
            item for item in value
            if isinstance(item, dict)
            and ("actionNumber" in item or "actionId" in item)
            and ("period" in item or "clock" in item or "actionType" in item)
        ]
        if direct:
            return direct
        combined: list[dict[str, Any]] = []
        for item in value:
            combined.extend(_find_action_rows(item))
        return combined
    if isinstance(value, dict):
        for key in ("actions", "playByPlay", "playbyplay", "game"):
            if key in value:
                found = _find_action_rows(value[key])
                if found:
                    return found
        for child in value.values():
            found = _find_action_rows(child)
            if found:
                return found
    return []


def _script_paths(html: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(r'''<script[^>]+src=["']([^"']+\.js(?:\?[^"']*)?)["']''', html, re.I)
    }


def _manifest_script_paths(text: str) -> set[str]:
    found: set[str] = set()
    patterns = (
        r'''["']((?:/_next/)?static/[^"']+?\.js)["']''',
        r'''["'](/_next/static/[^"']+?\.js)["']''',
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(1)
            if value.startswith("static/"):
                value = "/_next/" + value
            elif not value.startswith("/"):
                value = "/" + value
            found.add(value)
    return found


def _compact_context(text: str, start: int, end: int) -> str:
    lo = max(0, start - CONTEXT_RADIUS)
    hi = min(len(text), end + CONTEXT_RADIUS)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()


def _marker_hits(text: str) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for marker in DISCOVERY_MARKERS:
        pattern = re.compile(re.escape(marker), re.I)
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        results[marker] = {
            "count": len(matches),
            "contexts": [
                _compact_context(text, match.start(), match.end())
                for match in matches[:MAX_CONTEXTS_PER_MARKER]
            ],
        }
    return results


def _api_candidates(text: str) -> set[str]:
    candidates: set[str] = set()
    # Literal-ish same-origin API paths. This is intentionally conservative;
    # contexts around '/api/' are retained separately for concatenated builders.
    for match in re.finditer(r'''["'](/api/[A-Za-z0-9_./?=&%${}:\-]+)["']''', text):
        value = match.group(1)
        if len(value) <= 240:
            candidates.add(value)
    return candidates


def _safe_sample(action: dict[str, Any]) -> dict[str, Any]:
    wanted = (
        "actionNumber", "actionId", "period", "clock", "teamId", "teamTricode",
        "personId", "playerName", "playerNameI", "actionType", "subType",
        "description", "scoreHome", "scoreAway",
    )
    return {key: action.get(key) for key in wanted if key in action}


def main() -> None:
    off_state = {key: os.getenv(key, "").strip().casefold() == "false" for key in OFF_ENV}
    if not all(off_state.values()):
        raise RuntimeError("Rotation probe refused because a production activation flag is not OFF.")

    page_urls = {
        "game": f"{BASE_URL}/game/{GAME_ID}",
        "box_score": f"{BASE_URL}/game/{GAME_ID}/box-score",
        "play_by_play": f"{BASE_URL}/game/{GAME_ID}/play-by-play",
        "player": f"{BASE_URL}/player/{PLAYER_ID}",
    }

    page_reports: dict[str, Any] = {}
    page_payloads: dict[str, dict[str, Any]] = {}
    asset_paths: set[str] = set()
    build_ids: set[str] = set()

    with httpx.Client(headers=HEADERS, timeout=20.0, follow_redirects=True) as client:
        for label, url in page_urls.items():
            response = client.get(url)
            response.raise_for_status()
            payload = _next_data(response.text)
            page_payloads[label] = payload
            build_id = payload.get("buildId")
            if isinstance(build_id, str) and build_id:
                build_ids.add(build_id)
            scripts = _script_paths(response.text)
            asset_paths.update(scripts)
            props = payload.get("props")
            page_props = props.get("pageProps") if isinstance(props, dict) else None
            page_reports[label] = {
                "url": str(response.url),
                "status_code": response.status_code,
                "html_bytes": len(response.content),
                "build_id": build_id,
                "page_props_top_level_keys": sorted(page_props) if isinstance(page_props, dict) else [],
                "rotationish_key_hits": _walk_key_hits(page_props) if isinstance(page_props, dict) else [],
                "script_count": len(scripts),
            }

        # Build manifests frequently enumerate route chunks not directly visible
        # in one HTML response. Search each observed build ID.
        manifest_reports: list[dict[str, Any]] = []
        for build_id in sorted(build_ids):
            for suffix in ("_buildManifest.js", "_ssgManifest.js"):
                manifest_url = f"{BASE_URL}/_next/static/{build_id}/{suffix}"
                try:
                    response = client.get(manifest_url)
                    status = response.status_code
                    text = response.text if status == 200 else ""
                    discovered = _manifest_script_paths(text)
                    asset_paths.update(discovered)
                    manifest_reports.append({
                        "url": manifest_url,
                        "status_code": status,
                        "bytes": len(response.content),
                        "discovered_script_count": len(discovered),
                        "marker_hits": _marker_hits(text) if text else {},
                        "api_candidates": sorted(_api_candidates(text)) if text else [],
                    })
                except httpx.HTTPError as exc:
                    manifest_reports.append({
                        "url": manifest_url,
                        "error": type(exc).__name__,
                    })

        # Normalize to same-origin WNBA assets only.
        normalized_assets: set[str] = set()
        for value in asset_paths:
            absolute = urljoin(BASE_URL + "/", value)
            parsed = urlparse(absolute)
            if parsed.hostname == "www.wnba.com" and parsed.path.endswith(".js"):
                normalized_assets.add(absolute)

        asset_reports: list[dict[str, Any]] = []
        aggregate_marker_counts: Counter[str] = Counter()
        api_candidates: set[str] = set()
        rotation_candidate_assets: list[str] = []

        for url in sorted(normalized_assets)[:MAX_ASSETS]:
            entry: dict[str, Any] = {"url": url}
            try:
                response = client.get(url)
                entry["status_code"] = response.status_code
                entry["bytes"] = len(response.content)
                if response.status_code != 200:
                    asset_reports.append(entry)
                    continue
                if len(response.content) > MAX_ASSET_BYTES:
                    entry["skipped_reason"] = "asset_exceeds_scan_byte_cap"
                    asset_reports.append(entry)
                    continue
                text = response.text
                hits = _marker_hits(text)
                candidates = _api_candidates(text)
                entry["marker_hits"] = hits
                entry["api_candidates"] = sorted(candidates)
                for marker, data in hits.items():
                    aggregate_marker_counts[marker] += int(data["count"])
                api_candidates.update(candidates)
                if any(marker in hits for marker in EXACT_MARKERS) or any(
                    "rotation" in candidate.casefold() for candidate in candidates
                ):
                    rotation_candidate_assets.append(url)
            except httpx.HTTPError as exc:
                entry["error"] = type(exc).__name__
            asset_reports.append(entry)

    game_payload = page_payloads["game"]
    game_props = game_payload.get("props", {}).get("pageProps", {})
    pbp_surface = game_props.get("playByPlay") if isinstance(game_props, dict) else None
    raw_actions = _find_action_rows(pbp_surface)
    action_key_union = sorted({str(key) for action in raw_actions for key in action})
    rotationish_action_keys = sorted(key for key in action_key_union if _rotationish_key(key))
    substitutions = [
        action for action in raw_actions
        if str(action.get("actionType", "")).casefold() == "substitution"
        or "substitut" in str(action.get("description", "")).casefold()
    ]
    substitution_key_union = sorted({str(key) for action in substitutions for key in action})
    subtype_counts = Counter(str(action.get("subType")) for action in substitutions)
    team_counts = Counter(str(action.get("teamTricode")) for action in substitutions)

    game = game_props.get("game") if isinstance(game_props, dict) else None
    roster_reports: dict[str, Any] = {}
    if isinstance(game, dict):
        for side in ("homeTeam", "awayTeam"):
            team = game.get(side)
            players = team.get("players") if isinstance(team, dict) else None
            if isinstance(players, list):
                player_dicts = [player for player in players if isinstance(player, dict)]
                union = sorted({str(key) for player in player_dicts for key in player})
                roster_reports[side] = {
                    "player_count": len(player_dicts),
                    "player_key_union": union,
                    "rotationish_player_keys": sorted(key for key in union if _rotationish_key(key)),
                }

    exact_marker_totals = {
        marker: aggregate_marker_counts.get(marker, 0) for marker in EXACT_MARKERS
    }
    exact_contract_field_bundle_found = all(
        exact_marker_totals.get(marker, 0) > 0
        for marker in ("IN_TIME_REAL", "OUT_TIME_REAL", "PLAYER_PTS", "PT_DIFF", "USG_PCT")
    )
    rotation_api_candidates = sorted(
        candidate for candidate in api_candidates
        if "rotation" in candidate.casefold() or "stint" in candidate.casefold()
    )

    report = {
        "data_type": "wnba_step7g_exact_rotation_surface_probe",
        "created_at_utc": _now(),
        "read_only": True,
        "target_game_id": GAME_ID,
        "target_player_id": PLAYER_ID,
        "production_flags_off": off_state,
        "pages": page_reports,
        "build_ids": sorted(build_ids),
        "manifests": manifest_reports,
        "javascript_scan": {
            "asset_urls_discovered": len(normalized_assets),
            "asset_scan_cap": MAX_ASSETS,
            "assets_scanned_or_attempted": len(asset_reports),
            "aggregate_marker_counts": dict(sorted(aggregate_marker_counts.items())),
            "exact_marker_totals": exact_marker_totals,
            "exact_contract_field_bundle_found": exact_contract_field_bundle_found,
            "rotation_candidate_assets": rotation_candidate_assets,
            "all_literal_api_candidates": sorted(api_candidates),
            "rotation_api_candidates": rotation_api_candidates,
            "assets": asset_reports,
        },
        "raw_play_by_play": {
            "action_count": len(raw_actions),
            "action_key_union": action_key_union,
            "rotationish_action_keys": rotationish_action_keys,
            "substitution_action_count": len(substitutions),
            "substitution_key_union": substitution_key_union,
            "substitution_subtype_counts": dict(sorted(subtype_counts.items())),
            "substitution_team_counts": dict(sorted(team_counts.items())),
            "substitutions_missing_person_id": sum(action.get("personId") in (None, "") for action in substitutions),
            "substitutions_missing_clock": sum(action.get("clock") in (None, "") for action in substitutions),
            "substitution_samples": [_safe_sample(action) for action in substitutions[:8]],
        },
        "raw_rosters": roster_reports,
        "decision": {
            "exact_rotation_source_certified": False,
            "exact_contract_markers_found_in_assets": exact_contract_field_bundle_found,
            "rotation_endpoint_candidate_found": bool(rotation_api_candidates),
            "pbp_reconstruction_attempted": False,
            "pbp_reconstruction_certified_equivalent": False,
            "production_activation_allowed": False,
            "reason": (
                "This probe only discovers evidence. Exact Step 4R remains blocked until an "
                "official source can be invoked and parity-certified against source rotation stints."
            ),
        },
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "frozen_shared_provider_behavior_changed": False,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not raw_actions:
        raise RuntimeError("Rotation probe failed: official WNBA.com play-by-play actions were not available.")
    if not substitutions:
        raise RuntimeError("Rotation probe failed: no official substitution actions were observed in the target game.")

    print(json.dumps({
        "assets_discovered": len(normalized_assets),
        "assets_scanned": len(asset_reports),
        "exact_contract_field_bundle_found": exact_contract_field_bundle_found,
        "rotation_api_candidate_count": len(rotation_api_candidates),
        "pbp_action_count": len(raw_actions),
        "substitution_action_count": len(substitutions),
        "exact_rotation_source_certified": False,
        "production_activation_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
