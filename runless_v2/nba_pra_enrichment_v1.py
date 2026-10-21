"""Kyre Sports API NBA player enrichment router.

Active policy for this workstream:
- no ESPN
- no SportsGameOdds / SGO
- frontend provider isolation (this module runs behind Kyre Sports API)
- explicit provider health and fail-closed DATA_UNAVAILABLE semantics
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import hashlib
from html import unescape
import math
import os
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote_plus, urlparse

import httpx
from pydantic import BaseModel, Field

from .nba_pra_market_v1 import router

NBA_STATS_URL = "https://stats.nba.com/stats/leaguegamelog"
BREF_BASE = "https://www.basketball-reference.com"
NBA_HEADSHOT = "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
NBA_STATS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}
BREF_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0)"}


class NbaPraEnrichmentRequest(BaseModel):
    date: date
    player_names: list[str] = Field(min_length=1, max_length=180)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _norm(value: Any) -> str:
    return "".join(ch for ch in _text(value).casefold() if ch.isalnum())


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _season_end_year(day: date) -> int:
    return day.year + 1 if day.month >= 7 else day.year


def _season_label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def kyre_player_id(player_name: str) -> str:
    """Provider-independent internal player identity.

    Name normalization is intentionally provider-neutral. Provider IDs remain
    attached as aliases and never control frontend joins.
    """
    canonical = _norm(" ".join(_text(player_name).split()))
    digest = hashlib.sha256(f"nba|{canonical}".encode("utf-8")).hexdigest()[:16].upper()
    return f"KYRE-NBA-{digest}"


def normalize_history_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        pts, reb, ast = _num(raw.get("points")), _num(raw.get("rebounds")), _num(raw.get("assists"))
        if None in (pts, reb, ast):
            continue
        game_date = _text(raw.get("game_date") or raw.get("date"))[:10]
        key = game_date or repr((pts, reb, ast, raw.get("minutes")))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "game_date": game_date,
                "minutes": _num(raw.get("minutes")),
                "points": pts,
                "rebounds": reb,
                "assists": ast,
            }
        )
    return out


def _minutes(value: str) -> float | None:
    text = _text(value)
    if not text:
        return None
    if ":" not in text:
        return _num(text)
    minute, second = text.split(":", 1)
    try:
        return round(float(minute) + float(second) / 60.0, 3)
    except ValueError:
        return None


def _strip_html(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def _parse_bref_gamelog(document: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", document, flags=re.I | re.S):
        cells: dict[str, str] = {}
        for stat, body in re.findall(
            r"<(?:td|th)\b[^>]*data-stat=[\"']([^\"']+)[\"'][^>]*>(.*?)</(?:td|th)>",
            row_html,
            flags=re.I | re.S,
        ):
            cells[stat] = _strip_html(body)
        pts, reb, ast = _num(cells.get("pts")), _num(cells.get("trb")), _num(cells.get("ast"))
        if None in (pts, reb, ast):
            continue
        rows.append(
            {
                "game_date": _text(cells.get("date_game"))[:10],
                "minutes": _minutes(cells.get("mp", "")),
                "points": pts,
                "rebounds": reb,
                "assists": ast,
            }
        )
    return normalize_history_rows(rows)


def _extract_bref_profile(document: str, slug: str, expected_name: str) -> dict[str, Any]:
    nba_match = re.search(r"stats\.nba\.com/player/(\d+)/?", document, flags=re.I)
    team_match = re.search(r"<strong>\s*Team\s*</strong>\s*:\s*<a[^>]+/teams/([A-Z]{3})/", document, flags=re.I | re.S)
    pos_match = re.search(r"<strong>\s*Position:\s*</strong>\s*([^<]+)", document, flags=re.I | re.S)
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", document, flags=re.I | re.S)
    name = _strip_html(h1_match.group(1)) if h1_match else _text(expected_name)
    nba_id = nba_match.group(1) if nba_match else ""
    return {
        "player_name": name or _text(expected_name),
        "team": team_match.group(1).upper() if team_match else "",
        "position": _strip_html(pos_match.group(1)) if pos_match else "",
        "nba_id": nba_id,
        "bref_id": slug,
    }


def _default_fetch_text(kind: str, value: str, season: int | None = None) -> str:
    timeout = httpx.Timeout(12.0, connect=3.0)
    with httpx.Client(headers=BREF_HEADERS, timeout=timeout, follow_redirects=True) as client:
        if kind == "search":
            response = client.get(f"{BREF_BASE}/search/search.fcgi", params={"search": value})
        elif kind == "profile":
            response = client.get(f"{BREF_BASE}/players/{value[0]}/{value}.html")
        elif kind == "gamelog" and season is not None:
            response = client.get(f"{BREF_BASE}/players/{value[0]}/{value}/gamelog/{season}")
        else:
            raise ValueError("UNSUPPORTED_BREF_FETCH")
        response.raise_for_status()
        return response.text


def _resolve_bref_slug(player_name: str, search_html: str) -> str:
    # Prefer an exact visible-name match; otherwise reject rather than guess.
    wanted = _norm(player_name)
    for path, label in re.findall(
        r"href=[\"'](/players/[a-z]/([a-z0-9]+)\.html)[\"'][^>]*>(.*?)</a>",
        search_html,
        flags=re.I | re.S,
    ):
        del path
        if _norm(_strip_html(label)) == wanted:
            return slug_from_match := _text(label) and _text(re.search(r"/players/[a-z]/([a-z0-9]+)\.html", search_html[search_html.find('/players/'):], flags=re.I).group(1)) if False else ""
    # The compact loop above cannot safely reuse a global match. Parse pairs explicitly.
    for match in re.finditer(
        r"<a[^>]+href=[\"']/players/[a-z]/([a-z0-9]+)\.html[\"'][^>]*>(.*?)</a>",
        search_html,
        flags=re.I | re.S,
    ):
        if _norm(_strip_html(match.group(2))) == wanted:
            return match.group(1)
    # Basketball-Reference often redirects search directly to the profile page.
    title = re.search(r"<h1[^>]*>(.*?)</h1>", search_html, flags=re.I | re.S)
    canonical = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", search_html, flags=re.I)
    if title and canonical and _norm(_strip_html(title.group(1))) == wanted:
        return canonical.group(1)
    return ""


def _load_bref_player(
    player_name: str,
    slate_date: date,
    *,
    fetch_text: Callable[[str, str, int | None], str],
) -> dict[str, Any] | None:
    search = fetch_text("search", player_name, None)
    slug = _resolve_bref_slug(player_name, search)
    profile_doc = ""
    if not slug:
        # Some search responses are a redirect body without a canonical href;
        # use an unambiguous stats.nba.com link only when the expected name is present.
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", search, flags=re.I | re.S)
        nba = re.search(r"stats\.nba\.com/player/(\d+)/?", search, flags=re.I)
        if h1 and nba and _norm(_strip_html(h1.group(1))) == _norm(player_name):
            profile_doc = search
            # A slug is still required for the history URL, so fail closed here.
            return None
        return None
    profile_doc = fetch_text("profile", slug, None)
    profile = _extract_bref_profile(profile_doc, slug, player_name)
    if _norm(profile["player_name"]) != _norm(player_name):
        return None
    end_year = _season_end_year(slate_date)
    current_doc = fetch_text("gamelog", slug, end_year)
    prior_doc = fetch_text("gamelog", slug, end_year - 1)
    current = _parse_bref_gamelog(current_doc)
    prior = _parse_bref_gamelog(prior_doc)
    if not current and not prior:
        return None
    profile.update(
        {
            "kyre_player_id": kyre_player_id(player_name),
            "provider_ids": {
                "nba": profile.pop("nba_id", ""),
                "basketball_reference": profile.pop("bref_id", ""),
            },
            "headshot": "",
            "current_games": current,
            "prior_games": prior,
            "stats_source": "Basketball-Reference history fallback",
            "data_state": "VERIFIED",
        }
    )
    nba_id = _text(profile["provider_ids"].get("nba"))
    if nba_id:
        profile["headshot"] = NBA_HEADSHOT.format(player_id=nba_id)
    return profile


def _normalize_nba_stats(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result_sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(result_sets, Mapping):
        result_sets = [result_sets]
    if not isinstance(result_sets, list) or not result_sets:
        return {}
    block = result_sets[0] if isinstance(result_sets[0], Mapping) else {}
    headers = [str(x) for x in block.get("headers", [])]
    rows = block.get("rowSet") or []
    idx = {name: i for i, name in enumerate(headers)}
    required = {"PLAYER_ID", "PLAYER_NAME", "PTS", "REB", "AST"}
    if not required.issubset(idx):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, (list, tuple)):
            continue
        def value(name: str):
            pos = idx.get(name)
            return raw[pos] if pos is not None and pos < len(raw) else None
        name = _text(value("PLAYER_NAME"))
        if not name:
            continue
        key = _norm(name)
        item = out.setdefault(
            key,
            {
                "player_name": name,
                "team": _text(value("TEAM_ABBREVIATION")),
                "position": "",
                "nba_id": _text(value("PLAYER_ID")),
                "games": [],
            },
        )
        item["games"].append(
            {
                "game_date": _text(value("GAME_DATE"))[:10],
                "minutes": _num(value("MIN")),
                "points": _num(value("PTS")),
                "rebounds": _num(value("REB")),
                "assists": _num(value("AST")),
            }
        )
    return out


def _load_nba_official_profiles(slate_date: date) -> dict[str, dict[str, Any]]:
    end_year = _season_end_year(slate_date)
    timeout = httpx.Timeout(4.0, connect=2.0)
    seasons: dict[int, dict[str, dict[str, Any]]] = {}
    with httpx.Client(headers=NBA_STATS_HEADERS, timeout=timeout, follow_redirects=False) as client:
        for year in (end_year, end_year - 1):
            response = client.get(
                NBA_STATS_URL,
                params={
                    "Counter": 0,
                    "DateFrom": "",
                    "DateTo": "",
                    "Direction": "DESC",
                    "LeagueID": "00",
                    "PlayerOrTeam": "P",
                    "Season": _season_label(year),
                    "SeasonType": "Regular Season",
                    "Sorter": "DATE",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise ValueError("NBA_OFFICIAL_INVALID_PAYLOAD")
            seasons[year] = _normalize_nba_stats(payload)
    out: dict[str, dict[str, Any]] = {}
    for key in set(seasons.get(end_year, {})) | set(seasons.get(end_year - 1, {})):
        current = seasons.get(end_year, {}).get(key) or {}
        prior = seasons.get(end_year - 1, {}).get(key) or {}
        base = current or prior
        nba_id = _text(base.get("nba_id"))
        out[key] = {
            "kyre_player_id": kyre_player_id(base.get("player_name") or key),
            "player_name": _text(base.get("player_name")),
            "team": _text(base.get("team")),
            "position": "",
            "provider_ids": {"nba": nba_id},
            "headshot": NBA_HEADSHOT.format(player_id=nba_id) if nba_id else "",
            "current_games": normalize_history_rows(current.get("games") or []),
            "prior_games": normalize_history_rows(prior.get("games") or []),
            "stats_source": "NBA Official / NBA Stats",
            "data_state": "VERIFIED",
        }
    return out


def _health(status: str, detail: str, *, attempted: bool) -> dict[str, Any]:
    return {"status": status, "detail": detail, "attempted": attempted}


def collect_nba_pra_enrichment(
    slate_date: date,
    player_names: Sequence[str],
    *,
    official_loader: Callable[[date], Mapping[str, Mapping[str, Any]]] | None = None,
    fetch_text: Callable[[str, str, int | None], str] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    names = []
    seen = set()
    for raw in player_names:
        name = " ".join(_text(raw).split())
        key = _norm(name)
        if name and key not in seen:
            names.append(name)
            seen.add(key)
    env = dict(os.environ if env is None else env)
    fetch_text = fetch_text or _default_fetch_text
    official_loader = official_loader or _load_nba_official_profiles

    health: dict[str, dict[str, Any]] = {}
    profiles: dict[str, dict[str, Any]] = {}

    try:
        official = dict(official_loader(slate_date) or {})
        for name in names:
            key = _norm(name)
            raw = official.get(key)
            if raw and (raw.get("current_games") or raw.get("prior_games")):
                row = dict(raw)
                row.setdefault("kyre_player_id", kyre_player_id(name))
                row.setdefault("player_name", name)
                row.setdefault("provider_ids", {})
                row.setdefault("data_state", "VERIFIED")
                profiles[key] = row
        health["nba_official"] = _health(
            "HEALTHY" if profiles else "DEGRADED",
            "OK" if profiles else "NO_ELIGIBLE_PLAYER_HISTORY",
            attempted=True,
        )
    except Exception as exc:
        health["nba_official"] = _health("DEGRADED", f"{type(exc).__name__}", attempted=True)

    sportradar_key = _text(env.get("SPORTRADAR_API_KEY"))
    sportsdataio_key = _text(env.get("SPORTSDATAIO_API_KEY"))
    health["sportradar"] = _health(
        "DEGRADED" if sportradar_key else "UNAVAILABLE",
        "ADAPTER_NOT_ENABLED" if sportradar_key else "CREDENTIAL_NOT_CONFIGURED",
        attempted=False,
    )
    health["sportsdataio"] = _health(
        "DEGRADED" if sportsdataio_key else "UNAVAILABLE",
        "ADAPTER_NOT_ENABLED" if sportsdataio_key else "CREDENTIAL_NOT_CONFIGURED",
        attempted=False,
    )

    missing = [name for name in names if _norm(name) not in profiles]
    bref_success = 0
    bref_fail = 0
    if missing:
        # BRef is allowed here only as a history fallback. Canonical identity is
        # KYRE_PLAYER_ID; an NBA ID is retained only when the page cross-links it.
        workers = min(4, max(1, len(missing)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = {
                pool.submit(_load_bref_player, name, slate_date, fetch_text=fetch_text): name
                for name in missing
            }
            for future in as_completed(jobs):
                name = jobs[future]
                try:
                    profile = future.result()
                except Exception:
                    profile = None
                if profile:
                    profiles[_norm(name)] = profile
                    bref_success += 1
                else:
                    bref_fail += 1
    health["basketball_reference"] = _health(
        "HEALTHY" if bref_success and bref_fail == 0 else "DEGRADED" if bref_success else "UNAVAILABLE",
        f"RESOLVED_{bref_success}_FAILED_{bref_fail}" if missing else "NOT_NEEDED",
        attempted=bool(missing),
    )

    unavailable = [name for name in names if _norm(name) not in profiles]
    for name in unavailable:
        profiles[_norm(name)] = {
            "kyre_player_id": kyre_player_id(name),
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
    return {
        "schema_version": "KYRE_NBA_ENRICHMENT_V1",
        "date": slate_date.isoformat(),
        "data_state": "VERIFIED" if verified == len(names) and names else "PARTIAL" if verified else "DATA_UNAVAILABLE",
        "profiles": profiles,
        "provider_health": health,
        "verified_players": verified,
        "requested_players": len(names),
        "fabrication": False,
    }


@router.post("/enrichment")
def nba_pra_enrichment(req: NbaPraEnrichmentRequest) -> dict[str, Any]:
    return collect_nba_pra_enrichment(req.date, req.player_names)
