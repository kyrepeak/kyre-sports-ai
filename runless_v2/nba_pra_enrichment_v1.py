"""Kyre NBA enrichment routing surface."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
from typing import Any, Callable, Mapping, Sequence

from . import nba_pra_enrichment_core_v1 as _core
from .nba_pra_enrichment_core_v1 import *  # noqa: F401,F403
from .nba_pra_cbs_v1 import load_cbs_profiles

_TEAM_ALIASES = {"PHO": "PHX", "BRK": "BKN", "CHO": "CHA"}


def _resolve_search_slug(player_name: str, search_html: str) -> str:
    wanted = _core._norm(player_name)
    for match in re.finditer(
        r"<a[^>]+href=[\"']/players/[a-z]/([a-z0-9]+)\.html[\"'][^>]*>(.*?)</a>",
        search_html,
        flags=re.I | re.S,
    ):
        label = _core._strip_html(match.group(2))
        label = re.sub(r"\s*\(\d{4}-\d{4}\)\s*$", "", label)
        if _core._norm(label) == wanted:
            return match.group(1)
    return ""


_original_extract_profile = _core._extract_bref_profile


def _extract_profile(document: str, slug: str, expected_name: str):
    profile = _original_extract_profile(document, slug, expected_name)
    team = str(profile.get("team") or "").upper()
    profile["team"] = _TEAM_ALIASES.get(team, team)
    return profile


def _parse_real_game_rows(document: str):
    rows = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", document, flags=re.I | re.S):
        cells = {}
        for stat, body in re.findall(
            r"<(?:td|th)\b[^>]*data-stat=[\"']([^\"']+)[\"'][^>]*>(.*?)</(?:td|th)>",
            row_html,
            flags=re.I | re.S,
        ):
            cells[stat] = _core._strip_html(body)
        raw_date = str(cells.get("date_game") or "").strip()
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%b %d, %Y", "%m/%d/%Y"):
            try:
                from datetime import datetime
                parsed_date = datetime.strptime(raw_date, fmt).date().isoformat()
                break
            except ValueError:
                continue
        if parsed_date is None:
            continue
        pts = _core._num(cells.get("pts"))
        reb = _core._num(cells.get("trb"))
        ast = _core._num(cells.get("ast"))
        if pts is None or reb is None or ast is None:
            continue
        rows.append({
            "game_date": parsed_date,
            "minutes": _core._minutes(cells.get("mp", "")),
            "points": pts,
            "rebounds": reb,
            "assists": ast,
        })
    return _core.normalize_history_rows(rows)


_core._resolve_bref_slug = _resolve_search_slug
_core._extract_bref_profile = _extract_profile
_core._parse_bref_gamelog = _parse_real_game_rows


def _health(status: str, detail: str, attempted: bool) -> dict[str, Any]:
    return {"status": status, "detail": detail, "attempted": attempted}


def _normalize_names(player_names: Sequence[str]) -> list[str]:
    names = []
    seen = set()
    for raw in player_names:
        name = " ".join(str(raw or "").split())
        key = _core._norm(name)
        if name and key and key not in seen:
            names.append(name)
            seen.add(key)
    return names


def _valid_profile(row: Mapping[str, Any] | None) -> bool:
    return bool(row and (row.get("current_games") or row.get("prior_games")))


def _bounded_reference_profiles(
    slate_date,
    names: Sequence[str],
    *,
    fetch_text: Callable[[str, str, int | None], str] | None = None,
    max_players: int = 4,
) -> tuple[dict[str, dict[str, Any]], int]:
    """Last-resort bounded history fallback.

    It is intentionally capped because the provider is not safe for slate-scale
    per-player fan-out. The CBS stage is the normal no-key runtime fallback.
    """
    attempted = list(names[:max_players])
    if not attempted:
        return {}, 0
    fetch = fetch_text or _core._default_fetch_text
    out: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(2, len(attempted))) as pool:
        jobs = {
            pool.submit(_core._load_bref_player, name, slate_date, fetch_text=fetch): name
            for name in attempted
        }
        for future in as_completed(jobs):
            name = jobs[future]
            try:
                row = future.result()
            except Exception:
                row = None
            if _valid_profile(row):
                out[_core._norm(name)] = dict(row)
    return out, len(attempted)


def collect_nba_pra_enrichment(
    slate_date,
    player_names: Sequence[str],
    *,
    official_loader=None,
    cbs_loader=None,
    bref_loader=None,
    fetch_text=None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Route NBA enrichment by data quality, stopping after verified success."""
    names = _normalize_names(player_names)
    env_map = dict(os.environ if env is None else env)
    official = official_loader or _core._load_nba_official_profiles
    profiles: dict[str, dict[str, Any]] = {}
    health: dict[str, dict[str, Any]] = {}

    try:
        official_rows = dict(official(slate_date) or {})
        for name in names:
            key = _core._norm(name)
            row = official_rows.get(key)
            if not _valid_profile(row):
                continue
            normalized = dict(row)
            normalized.setdefault("kyre_player_id", _core.kyre_player_id(name))
            normalized.setdefault("player_name", name)
            normalized.setdefault("provider_ids", {})
            normalized.setdefault("data_state", "VERIFIED")
            profiles[key] = normalized
        health["nba_official"] = _health(
            "HEALTHY" if profiles else "DEGRADED",
            "OK" if profiles else "NO_ELIGIBLE_PLAYER_HISTORY",
            True,
        )
    except Exception as exc:
        health["nba_official"] = _health("DEGRADED", type(exc).__name__, True)

    # Licensed sources stay in the ordered router but are never called without
    # configured credentials/adapters.
    sr_key = str(env_map.get("SPORTRADAR_API_KEY") or "").strip()
    sd_key = str(env_map.get("SPORTSDATAIO_API_KEY") or "").strip()
    health["sportradar"] = _health(
        "DEGRADED" if sr_key else "UNAVAILABLE",
        "ADAPTER_NOT_ENABLED" if sr_key else "CREDENTIAL_NOT_CONFIGURED",
        False,
    )
    health["sportsdataio"] = _health(
        "DEGRADED" if sd_key else "UNAVAILABLE",
        "ADAPTER_NOT_ENABLED" if sd_key else "CREDENTIAL_NOT_CONFIGURED",
        False,
    )

    missing = [name for name in names if _core._norm(name) not in profiles]
    cbs_rows: dict[str, dict[str, Any]] = {}
    if missing:
        try:
            # Custom fetch_text implies a deterministic reference-provider test;
            # production uses the approved CBS runtime fallback by default.
            if cbs_loader is not None:
                cbs_rows = dict(cbs_loader(slate_date, missing) or {})
            elif fetch_text is None:
                cbs_rows = dict(load_cbs_profiles(slate_date, missing) or {})
        except Exception:
            cbs_rows = {}
        for name in missing:
            key = _core._norm(name)
            row = cbs_rows.get(key)
            if not _valid_profile(row):
                continue
            normalized = dict(row)
            normalized["kyre_player_id"] = _core.kyre_player_id(name)
            normalized.setdefault("player_name", name)
            normalized.setdefault("provider_ids", {})
            normalized.setdefault("data_state", "VERIFIED")
            profiles[key] = normalized
    cbs_requested = bool(missing) and (cbs_loader is not None or fetch_text is None)
    cbs_resolved = sum(1 for name in missing if _core._norm(name) in profiles)
    health["cbs_sports"] = _health(
        "HEALTHY" if cbs_requested and cbs_resolved == len(missing) and missing else "DEGRADED" if cbs_resolved else "UNAVAILABLE",
        "NOT_NEEDED" if not missing else f"RESOLVED_{cbs_resolved}_OF_{len(missing)}" if cbs_requested else "TEST_INJECTION_SKIPPED",
        cbs_requested,
    )

    still_missing = [name for name in names if _core._norm(name) not in profiles]
    reference_rows: dict[str, dict[str, Any]] = {}
    attempted_reference = 0
    if still_missing:
        try:
            if bref_loader is not None:
                reference_rows = dict(bref_loader(slate_date, still_missing) or {})
                attempted_reference = len(still_missing)
            else:
                reference_rows, attempted_reference = _bounded_reference_profiles(
                    slate_date,
                    still_missing,
                    fetch_text=fetch_text,
                )
        except Exception:
            reference_rows = {}
        for name in still_missing:
            key = _core._norm(name)
            row = reference_rows.get(key)
            if not _valid_profile(row):
                continue
            normalized = dict(row)
            normalized.setdefault("kyre_player_id", _core.kyre_player_id(name))
            normalized.setdefault("player_name", name)
            normalized.setdefault("provider_ids", {})
            normalized.setdefault("data_state", "VERIFIED")
            profiles[key] = normalized
    ref_resolved = sum(1 for name in still_missing if _core._norm(name) in profiles)
    health["basketball_reference"] = _health(
        "HEALTHY" if attempted_reference and ref_resolved == len(still_missing) else "DEGRADED" if ref_resolved else "UNAVAILABLE",
        "NOT_NEEDED" if not still_missing else f"RESOLVED_{ref_resolved}_ATTEMPTED_{attempted_reference}_MISSING_{len(still_missing)}",
        attempted_reference > 0,
    )

    for name in names:
        key = _core._norm(name)
        if key in profiles:
            continue
        profiles[key] = {
            "kyre_player_id": _core.kyre_player_id(name),
            "player_name": name,
            "team": "",
            "position": "",
            "provider_ids": {},
            "headshot": "",
            "current_games": [],
            "prior_games": [],
            "stats_source": "DATA_UNAVAILABLE",
            "data_state": "DATA_UNAVAILABLE",
        }

    verified = sum(1 for row in profiles.values() if row.get("data_state") == "VERIFIED")
    state = "VERIFIED" if names and verified == len(names) else "PARTIAL" if verified else "DATA_UNAVAILABLE"
    return {
        "schema_version": "KYRE_NBA_ENRICHMENT_V1",
        "date": slate_date.isoformat(),
        "data_state": state,
        "profiles": profiles,
        "provider_health": health,
        "verified_players": verified,
        "requested_players": len(names),
        "fabrication": False,
    }


# The route was registered by the core module. Its endpoint resolves this module
# global at request time through the core namespace, so patch the single router
# authority rather than mounting a duplicate endpoint.
_core.collect_nba_pra_enrichment = collect_nba_pra_enrichment
