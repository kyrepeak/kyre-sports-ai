"""OFF-only schema probe for first-party WNBA advanced-stat surfaces.

The probe records only structural key paths and basic response metadata from
official WNBA.com pages. It does not persist player statistics, activate any
runtime, or call a sportsbook. The goal is to identify a genuine first-party
source before designing a Step-4F adapter.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

import httpx

from sports_api.wnba_step7g_first_party_history import _player_page

REPORT_PATH = Path("step7g-advanced-surface-probe.json")
PLAYER_ID = 1642785
URLS = (
    "https://www.wnba.com/stats/player-stats-advanced?Season=2026&SeasonType=Regular%20Season",
    "https://www.wnba.com/stats/team-stats-advanced?Season=2026&SeasonType=Regular%20Season",
)
TOKENS = (
    "rating", "pace", "usage", "usg", "true", "effective", "efg", "ts_pct",
    "rebound", "reb_pct", "poss", "pie", "assist", "turnover",
)
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _assert_safe() -> None:
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError("Advanced probe refuses production-enabled environment: " + ", ".join(bad))


def _matching_key_paths(value: Any, path: str = "root", *, limit: int = 500) -> list[str]:
    out: list[str] = []
    def walk(item: Any, current: str) -> None:
        if len(out) >= limit:
            return
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = str(key)
                next_path = f"{current}.{key_text}"
                folded = key_text.casefold()
                if any(token in folded for token in TOKENS):
                    out.append(next_path)
                    if len(out) >= limit:
                        return
                walk(child, next_path)
        elif isinstance(item, list):
            for index, child in enumerate(item[:25]):
                walk(child, f"{current}[{index}]")
                if len(out) >= limit:
                    return
    walk(value, path)
    return sorted(set(out))


def _next_data_from_html(text: str) -> dict[str, Any] | None:
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _keys(value: Any) -> list[str]:
    return sorted(str(key) for key in value.keys()) if isinstance(value, dict) else []


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    _, player, _, _, _, player_url = _player_page(PLAYER_ID)
    surfaces: list[dict[str, Any]] = []
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-Step7G-Cert/1.0)",
    }
    for url in URLS:
        row: dict[str, Any] = {"url": url}
        try:
            response = httpx.get(url, headers=headers, timeout=20.0, follow_redirects=True)
            row["http_status"] = response.status_code
            row["final_url"] = str(response.url)
            row["content_type"] = response.headers.get("content-type")
            row["body_length"] = len(response.text)
            response.raise_for_status()
            next_data = _next_data_from_html(response.text)
            row["next_data_present"] = next_data is not None
            row["next_data_top_level_keys"] = _keys(next_data)
            row["matching_key_paths"] = _matching_key_paths(next_data) if next_data else []
            folded_body = response.text.casefold()
            row["body_token_presence"] = {
                token: token in folded_body for token in TOKENS
            }
            row["next_data_script_count"] = len(
                re.findall(r'__next_data__', folded_body)
            )
            row["next_flight_marker_present"] = "self.__next_f.push" in folded_body
        except Exception as exc:
            row["error_type"] = type(exc).__name__
            row["error_message"] = str(exc)[:500]
        surfaces.append(row)

    stats = player.get("stats") if isinstance(player, dict) else None
    career = player.get("careerStats") if isinstance(player, dict) else None
    report = {
        "data_type": "wnba_step7g_advanced_first_party_surface_probe_v2",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "player_page": {
            "url": player_url,
            "matching_key_paths": _matching_key_paths(player),
            "top_level_keys": _keys(player),
            "stats_keys": _keys(stats),
            "stats_matching_key_paths": _matching_key_paths(stats, "player.stats"),
            "career_stats_type": type(career).__name__,
            "career_stats_matching_key_paths": _matching_key_paths(career, "player.careerStats"),
        },
        "stats_pages": surfaces,
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "persistence_performed": False,
            "supabase_mutation_performed": False,
            "probe_contains_only_schema_metadata": True,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
