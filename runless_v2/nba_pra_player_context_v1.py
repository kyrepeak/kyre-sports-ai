"""Kyre Sports API NBA player-context router."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
import hashlib
import html as html_lib
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/nba/pra/player-context", tags=["nba-pra-player-context"])

REFERENCE_ROOT = "https://www.basketball-reference.com"
REFERENCE_SEARCH = f"{REFERENCE_ROOT}/search/search.fcgi"
REFERENCE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0)",
    "Accept": "text/html,application/xhtml+xml",
}


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split())


def _norm(value: Any) -> str:
    return "".join(ch for ch in _text(value).casefold() if ch.isalnum())


def kyre_player_id(player_name: str, team: str = "", league: str = "NBA") -> str:
    """Return a stable Kyre identity that never depends on a provider ID."""
    del team
    league_key = _norm(league).upper() or "NBA"
    name_key = _norm(player_name)
    digest = hashlib.sha256(f"{league_key}|{name_key}".encode("utf-8")).hexdigest()[:16].upper()
    return f"KPID-{league_key}-{digest}"


def _history_ok(row: Mapping[str, Any] | None) -> bool:
    return bool(row and (row.get("current_games") or row.get("prior_games")))


def _normalize_profile(name: str, row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["player_name"] = _text(out.get("player_name") or name)
    out["team"] = _text(out.get("team")).upper()
    out["position"] = _text(out.get("position"))
    out["provider_ids"] = dict(out.get("provider_ids") or {})
    out["headshot"] = _text(out.get("headshot"))
    out["current_games"] = list(out.get("current_games") or [])
    out["prior_games"] = list(out.get("prior_games") or [])
    out["kyre_player_id"] = kyre_player_id(out["player_name"], out["team"], "NBA")
    out["data_state"] = "VERIFIED" if _history_ok(out) else "DATA_UNAVAILABLE"
    return out


def _health(status: str, detail: str, attempted: bool) -> dict[str, Any]:
    return {"status": status, "detail": detail, "attempted": attempted}


def _coerce_provider_payload(value: Any) -> tuple[str, dict[str, dict[str, Any]], str]:
    if not isinstance(value, Mapping):
        return "DEGRADED", {}, "INVALID_PAYLOAD"
    if isinstance(value.get("profiles"), Mapping):
        rows = {str(k): dict(v) for k, v in value["profiles"].items() if isinstance(v, Mapping)}
        status = _text(value.get("status") or ("HEALTHY" if rows else "DEGRADED")).upper()
        detail = _text(value.get("diagnostic_state") or value.get("detail") or ("OK" if rows else "NO_DATA"))
        return status, rows, detail
    rows = {str(k): dict(v) for k, v in value.items() if isinstance(v, Mapping)}
    return ("HEALTHY" if rows else "DEGRADED"), rows, ("OK" if rows else "NO_DATA")


def _official_profiles(slate_date: date, names: Sequence[str]) -> dict[str, Any]:
    from nba_pra_page1_sources_v2 import load_nba_stats_profiles

    all_rows = dict(load_nba_stats_profiles(slate_date) or {})
    wanted = {_norm(name) for name in names}
    rows = {key: value for key, value in all_rows.items() if key in wanted}
    return {
        "status": "HEALTHY" if rows else "DEGRADED",
        "diagnostic_state": "OK" if rows else "NO_ELIGIBLE_HISTORY",
        "profiles": rows,
    }


def _season_end_year(day: date) -> int:
    return day.year + 1 if day.month >= 10 else day.year


def _get_text(url: str, *, params: Mapping[str, Any] | None = None, timeout: float = 8.0) -> tuple[str, str]:
    with httpx.Client(headers=REFERENCE_HEADERS, timeout=httpx.Timeout(timeout, connect=3.0), follow_redirects=True) as client:
        response = client.get(url, params=dict(params or {}))
        response.raise_for_status()
        return response.text, str(response.url)


def _strip_tags(value: str) -> str:
    return _text(html_lib.unescape(re.sub(r"<[^>]+>", " ", value or "")))


def _resolve_reference_slug(player_name: str) -> str:
    document, final_url = _get_text(REFERENCE_SEARCH, params={"search": player_name})
    direct = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", final_url, flags=re.I)
    if direct:
        return direct.group(1).casefold()
    wanted = _norm(player_name)
    for match in re.finditer(
        r"<a[^>]+href=[\"'](/players/[a-z]/([a-z0-9]+)\.html)[\"'][^>]*>(.*?)</a>",
        document,
        flags=re.I | re.S,
    ):
        label = re.sub(r"\s*\(\d{4}-\d{4}\)\s*$", "", _strip_tags(match.group(3)))
        if _norm(label) == wanted:
            return match.group(2).casefold()
    return ""


def _profile_meta(document: str, slug: str) -> tuple[str, str, str]:
    team_match = re.search(
        r"<strong>\s*Team\s*:?[ ]*</strong>\s*:?\s*<a[^>]+href=[\"']/teams/([A-Z]{2,3})/\d{4}\.html",
        document,
        flags=re.I | re.S,
    )
    team = team_match.group(1).upper() if team_match else ""
    position_match = re.search(r"<strong>\s*Position:\s*</strong>\s*(.*?)(?:<br\s*/?>|</p>)", document, flags=re.I | re.S)
    position = _strip_tags(position_match.group(1)) if position_match else ""
    image = ""
    for pattern in (
        r"<meta[^>]+property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)",
        r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+property=[\"']og:image[\"']",
    ):
        match = re.search(pattern, document, flags=re.I | re.S)
        if match:
            image = urljoin(REFERENCE_ROOT, html_lib.unescape(match.group(1)))
            break
    return team, position, image


def _num(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _minutes(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    if ":" in text:
        left, right = text.split(":", 1)
        try:
            return round(float(left) + float(right) / 60.0, 3)
        except ValueError:
            return None
    return _num(text)


def _parse_game_log(document: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", document, flags=re.I | re.S):
        cells: dict[str, str] = {}
        for stat, body in re.findall(
            r"<(?:td|th)\b[^>]*data-stat=[\"']([^\"']+)[\"'][^>]*>(.*?)</(?:td|th)>",
            row_html,
            flags=re.I | re.S,
        ):
            cells[stat] = _strip_tags(body)
        game_date = _text(cells.get("date_game") or cells.get("date"))
        pts, reb, ast = _num(cells.get("pts")), _num(cells.get("trb")), _num(cells.get("ast"))
        if not game_date or pts is None or reb is None or ast is None:
            continue
        rows.append(
            {
                "game_date": game_date,
                "minutes": _minutes(cells.get("mp")),
                "points": pts,
                "rebounds": reb,
                "assists": ast,
            }
        )
    rows.sort(key=lambda row: str(row.get("game_date") or ""), reverse=True)
    return rows[:40]


def _reference_player(player_name: str, slate_date: date) -> dict[str, Any] | None:
    slug = _resolve_reference_slug(player_name)
    if not slug:
        return None
    letter = slug[0]
    profile_html, _ = _get_text(f"{REFERENCE_ROOT}/players/{letter}/{slug}.html")
    team, position, headshot = _profile_meta(profile_html, slug)
    end_year = _season_end_year(slate_date)
    current_games: list[dict[str, Any]] = []
    prior_games: list[dict[str, Any]] = []
    for season, target in ((end_year, current_games), (end_year - 1, prior_games)):
        try:
            document, _ = _get_text(f"{REFERENCE_ROOT}/players/{letter}/{slug}/gamelog/{season}")
            target.extend(_parse_game_log(document))
        except Exception:
            continue
    if not current_games and not prior_games:
        return None
    return {
        "player_name": player_name,
        "team": team,
        "position": position,
        "provider_ids": {"basketball_reference": slug},
        "headshot": headshot,
        "current_games": current_games,
        "prior_games": prior_games,
        "stats_source": "Basketball-Reference",
    }


def _reference_profiles(slate_date: date, names: Sequence[str]) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    if names:
        with ThreadPoolExecutor(max_workers=min(4, len(names))) as pool:
            jobs = {pool.submit(_reference_player, name, slate_date): name for name in names}
            for future in as_completed(jobs):
                name = jobs[future]
                try:
                    row = future.result()
                except Exception:
                    row = None
                if row:
                    rows[_norm(name)] = row
    return {
        "status": "HEALTHY" if rows and len(rows) == len(names) else "DEGRADED",
        "diagnostic_state": f"RESOLVED_{len(rows)}_OF_{len(names)}",
        "profiles": rows,
    }


def _merge_provider_rows(
    profiles: dict[str, dict[str, Any]],
    requested: Sequence[str],
    raw_rows: Mapping[str, Mapping[str, Any]],
) -> int:
    added = 0
    for name in requested:
        key = _norm(name)
        if key in profiles:
            continue
        row = raw_rows.get(key)
        if not isinstance(row, Mapping) or not _history_ok(row):
            continue
        profiles[key] = _normalize_profile(name, row)
        added += 1
    return added


def collect_nba_pra_player_context(
    slate_date: date,
    player_names: Sequence[str],
    *,
    official_loader: Callable[[date, Sequence[str]], Any] | None = None,
    licensed_loaders: Sequence[Any] | None = None,
    basketball_reference_loader: Callable[[date, Sequence[str]], Any] | None = None,
) -> dict[str, Any]:
    names: list[str] = []
    seen: set[str] = set()
    for raw in player_names:
        name = _text(raw)
        key = _norm(name)
        if name and key and key not in seen:
            names.append(name)
            seen.add(key)

    profiles: dict[str, dict[str, Any]] = {}
    health: dict[str, dict[str, Any]] = {}
    official = official_loader or _official_profiles
    try:
        status, rows, detail = _coerce_provider_payload(official(slate_date, names))
        _merge_provider_rows(profiles, names, rows)
        health["nba_official"] = _health(status, detail, True)
    except Exception as exc:
        health["nba_official"] = _health("DEGRADED", type(exc).__name__, True)

    missing = [name for name in names if _norm(name) not in profiles]
    licensed = list(licensed_loaders or [])
    if not licensed:
        health["sportradar"] = _health("UNAVAILABLE", "ADAPTER_NOT_CONFIGURED", False)
        health["sportsdataio"] = _health("UNAVAILABLE", "ADAPTER_NOT_CONFIGURED", False)
    for index, entry in enumerate(licensed):
        if not missing:
            break
        if isinstance(entry, tuple) and len(entry) == 2:
            provider_name, loader = str(entry[0]), entry[1]
        else:
            loader = entry
            provider_name = getattr(loader, "__name__", None) or f"licensed_{index + 1}"
        try:
            status, rows, detail = _coerce_provider_payload(loader(slate_date, missing))
            _merge_provider_rows(profiles, missing, rows)
            health[provider_name] = _health(status, detail, True)
        except Exception as exc:
            health[provider_name] = _health("DEGRADED", type(exc).__name__, True)
        missing = [name for name in names if _norm(name) not in profiles]

    reference = basketball_reference_loader or _reference_profiles
    if missing:
        try:
            status, rows, detail = _coerce_provider_payload(reference(slate_date, missing))
            _merge_provider_rows(profiles, missing, rows)
            health["basketball_reference"] = _health(status, detail, True)
        except Exception as exc:
            health["basketball_reference"] = _health("DEGRADED", type(exc).__name__, True)
    else:
        health["basketball_reference"] = _health("HEALTHY", "NOT_NEEDED", False)

    for name in names:
        key = _norm(name)
        if key in profiles:
            continue
        profiles[key] = {
            "kyre_player_id": kyre_player_id(name, "", "NBA"),
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
    verification = "VERIFIED" if names and verified == len(names) else "PARTIAL" if verified else "DATA_UNAVAILABLE"
    return {
        "schema_version": "KYRE_NBA_PLAYER_CONTEXT_V1",
        "date": slate_date.isoformat(),
        "verification": verification,
        "profiles": profiles,
        "provider_health": health,
        "verified_players": verified,
        "requested_players": len(names),
        "fabrication": False,
    }


class NbaPraPlayerContextRequest(BaseModel):
    date: date
    player_names: list[str] = Field(min_length=1, max_length=120)


@router.post("")
def player_context(request: NbaPraPlayerContextRequest) -> dict[str, Any]:
    return collect_nba_pra_player_context(request.date, request.player_names)
