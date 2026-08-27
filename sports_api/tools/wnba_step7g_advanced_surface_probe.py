"""OFF-only structural probe for first-party WNBA advanced-stat transport.

The public WNBA.com advanced-stat pages are client-loaded. This probe records
only page/asset metadata, structural key paths, endpoint-like literal strings,
and token presence from WNBA.com's own HTML/JavaScript. It does not persist
player/team statistic values, activate runtime, call sportsbooks, or mutate any
storage. Its purpose is to discover the genuine first-party transport used by
those official pages before implementing Step 4F.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from sports_api.wnba_step7g_first_party_history import _player_page

REPORT_PATH = Path("step7g-advanced-surface-probe.json")
PLAYER_ID = 1642785
URLS = (
    "https://www.wnba.com/stats/player-stats-advanced?Season=2026&SeasonType=Regular%20Season",
    "https://www.wnba.com/stats/team-stats-advanced?Season=2026&SeasonType=Regular%20Season",
)
TOKENS = (
    "leaguedashplayerstats",
    "leaguedashteamstats",
    "measuretype",
    "advanced",
    "off_rating",
    "def_rating",
    "net_rating",
    "ast_pct",
    "ast_to",
    "ast_ratio",
    "oreb_pct",
    "dreb_pct",
    "reb_pct",
    "tm_tov_pct",
    "efg_pct",
    "ts_pct",
    "usg_pct",
    "pace",
    "pie",
    "stats.wnba.com",
    "stats.nba.com",
)
MAX_ASSETS = 45
MAX_ASSET_BYTES = 4_000_000
MAX_ENDPOINT_LITERALS = 120
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
    key_tokens = (
        "rating", "pace", "usage", "usg", "true", "effective", "efg", "ts_pct",
        "rebound", "reb_pct", "poss", "pie", "assist", "turnover",
    )

    def walk(item: Any, current: str) -> None:
        if len(out) >= limit:
            return
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = str(key)
                next_path = f"{current}.{key_text}"
                folded = key_text.casefold()
                if any(token in folded for token in key_tokens):
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


def _script_urls(html: str, base_url: str) -> list[str]:
    values = re.findall(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )
    out: list[str] = []
    for value in values:
        absolute = urljoin(base_url, unescape(value))
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.hostname not in {"www.wnba.com", "cdn.nba.com", "cdn.wnba.com"}:
            continue
        if absolute not in out:
            out.append(absolute)
    return out[:MAX_ASSETS]


def _endpoint_literals(text: str) -> list[str]:
    candidates: set[str] = set()
    patterns = (
        r'https?://[^"\'\s<>\\]{4,260}',
        r'/(?:api|stats)/[^"\'\s<>\\]{2,220}',
        r'(?:league|boxscore|player|team)[a-z0-9_-]{4,80}',
    )
    for pattern in patterns:
        for raw in re.findall(pattern, text, flags=re.IGNORECASE):
            value = unescape(str(raw)).strip()
            folded = value.casefold()
            if any(
                marker in folded
                for marker in (
                    "stats", "league", "advanced", "playerstats", "teamstats",
                    "rating", "pace", "pie", "measuretype",
                )
            ):
                candidates.add(value[:300])
            if len(candidates) >= MAX_ENDPOINT_LITERALS:
                break
        if len(candidates) >= MAX_ENDPOINT_LITERALS:
            break
    return sorted(candidates)[:MAX_ENDPOINT_LITERALS]


def _asset_probe(client: httpx.Client, url: str) -> dict[str, Any]:
    row: dict[str, Any] = {"url": url}
    try:
        response = client.get(url)
        row["http_status"] = response.status_code
        row["content_type"] = response.headers.get("content-type")
        body = response.content[:MAX_ASSET_BYTES]
        row["bytes_scanned"] = len(body)
        if response.status_code != 200:
            return row
        text = body.decode("utf-8", errors="ignore")
        folded = text.casefold()
        matched = [token for token in TOKENS if token in folded]
        row["matched_tokens"] = matched
        if matched:
            row["endpoint_literals"] = _endpoint_literals(text)
    except Exception as exc:
        row["error_type"] = type(exc).__name__
        row["error_message"] = str(exc)[:300]
    return row


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    _, player, _, _, _, player_url = _player_page(PLAYER_ID)
    surfaces: list[dict[str, Any]] = []
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/javascript,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-Step7G-Cert/1.0)",
    }
    with httpx.Client(headers=headers, timeout=25.0, follow_redirects=True) as client:
        for url in URLS:
            row: dict[str, Any] = {"url": url}
            try:
                response = client.get(url)
                row["http_status"] = response.status_code
                row["final_url"] = str(response.url)
                row["content_type"] = response.headers.get("content-type")
                row["body_length"] = len(response.text)
                response.raise_for_status()
                next_data = _next_data_from_html(response.text)
                row["next_data_present"] = next_data is not None
                row["next_data_top_level_keys"] = _keys(next_data)
                row["next_data_props_keys"] = _keys(
                    next_data.get("props") if isinstance(next_data, dict) else None
                )
                row["matching_key_paths"] = _matching_key_paths(next_data) if next_data else []
                folded_body = response.text.casefold()
                row["body_token_presence"] = {
                    token: token in folded_body for token in TOKENS
                }
                scripts = _script_urls(response.text, str(response.url))
                row["script_count"] = len(scripts)
                asset_rows = [_asset_probe(client, script) for script in scripts]
                row["assets_with_transport_tokens"] = [
                    asset for asset in asset_rows if asset.get("matched_tokens")
                ]
                combined_literals: set[str] = set(_endpoint_literals(response.text))
                for asset in row["assets_with_transport_tokens"]:
                    combined_literals.update(asset.get("endpoint_literals") or [])
                row["combined_endpoint_literals"] = sorted(combined_literals)[:MAX_ENDPOINT_LITERALS]
            except Exception as exc:
                row["error_type"] = type(exc).__name__
                row["error_message"] = str(exc)[:500]
            surfaces.append(row)

    stats = player.get("stats") if isinstance(player, dict) else None
    career = player.get("careerStats") if isinstance(player, dict) else None
    report = {
        "data_type": "wnba_step7g_advanced_first_party_surface_probe_v3",
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
            "only_official_wnba_nba_cdn_assets_scanned": True,
            "probe_contains_only_schema_and_transport_metadata": True,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
