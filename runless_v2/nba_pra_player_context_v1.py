"""Kyre Sports API NBA player-context router."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
import hashlib
import html as html_lib
import re
import time
import unicodedata
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/nba/pra/player-context", tags=["nba-pra-player-context"])

REFERENCE_ROOT = "https://www.basketball-reference.com"
REFERENCE_SEARCH = f"{REFERENCE_ROOT}/search/search.fcgi"
REFERENCE_HISTORY_BUDGET = 8
REFERENCE_IDENTITY_SEARCH_BUDGET = 16
REFERENCE_HEADSHOT_TEMPLATE = f"{REFERENCE_ROOT}/req/202106291/images/headshots/{{slug}}.jpg"
REFERENCE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0)",
    "Accept": "text/html,application/xhtml+xml",
}
CBS_ROOT = "https://www.cbssports.com"
CBS_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0)", "Accept": "text/html,application/xhtml+xml"}
CBS_TEAM_ROSTERS = {
    "ATL": ("ATL", "atlanta-hawks"), "BOS": ("BOS", "boston-celtics"), "BKN": ("BKN", "brooklyn-nets"),
    "CHA": ("CHA", "charlotte-hornets"), "CHI": ("CHI", "chicago-bulls"), "CLE": ("CLE", "cleveland-cavaliers"),
    "DAL": ("DAL", "dallas-mavericks"), "DEN": ("DEN", "denver-nuggets"), "DET": ("DET", "detroit-pistons"),
    "GSW": ("GS", "golden-state-warriors"), "HOU": ("HOU", "houston-rockets"), "IND": ("IND", "indiana-pacers"),
    "LAC": ("LAC", "los-angeles-clippers"), "LAL": ("LAL", "los-angeles-lakers"), "MEM": ("MEM", "memphis-grizzlies"),
    "MIA": ("MIA", "miami-heat"), "MIL": ("MIL", "milwaukee-bucks"), "MIN": ("MIN", "minnesota-timberwolves"),
    "NOP": ("NO", "new-orleans-pelicans"), "NYK": ("NY", "new-york-knicks"), "OKC": ("OKC", "oklahoma-city-thunder"),
    "ORL": ("ORL", "orlando-magic"), "PHI": ("PHI", "philadelphia-76ers"), "PHX": ("PHO", "phoenix-suns"),
    "POR": ("POR", "portland-trail-blazers"), "SAC": ("SAC", "sacramento-kings"), "SAS": ("SA", "san-antonio-spurs"),
    "TOR": ("TOR", "toronto-raptors"), "UTA": ("UTA", "utah-jazz"), "WAS": ("WAS", "washington-wizards"),
}


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split())


def _norm(value: Any) -> str:
    folded = unicodedata.normalize("NFKD", _text(value).casefold())
    ascii_text = folded.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_text if ch.isalnum())


def _name_parts(value: Any) -> tuple[str, tuple[str, ...]]:
    folded = unicodedata.normalize("NFKD", _text(value).casefold()).encode("ascii", "ignore").decode("ascii")
    parts = tuple(re.findall(r"[a-z0-9]+", folded))
    suffixes = {"jr", "sr", "ii", "iii", "iv"}
    trimmed = parts[:-1] if parts and parts[-1] in suffixes else parts
    if not trimmed:
        return "", ()
    return trimmed[0], trimmed[1:]


def _match_reference_identity(name: str, rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    exact = rows.get(_norm(name))
    if isinstance(exact, Mapping):
        return dict(exact)
    first, remainder = _name_parts(name)
    if not first or not remainder:
        return None
    candidates: list[dict[str, Any]] = []
    for row in rows.values():
        if not isinstance(row, Mapping):
            continue
        row_first, row_remainder = _name_parts(row.get("player_name"))
        if row_remainder != remainder:
            continue
        first_ok = row_first == first or (len(first) == 1 and row_first.startswith(first))
        if first_ok:
            candidates.append(dict(row))
    return candidates[0] if len(candidates) == 1 else None


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
    has_identity = bool(out["team"] or out["position"] or out["headshot"] or out["provider_ids"])
    out["data_state"] = "VERIFIED" if _history_ok(out) else "IDENTITY_ONLY" if has_identity else "DATA_UNAVAILABLE"
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


def _get_text(url: str, *, params: Mapping[str, Any] | None = None, timeout: float = 8.0, headers: Mapping[str, str] | None = None) -> tuple[str, str]:
    with httpx.Client(headers=dict(headers or REFERENCE_HEADERS), timeout=httpx.Timeout(timeout, connect=3.0), follow_redirects=True) as client:
        response = client.get(url, params=dict(params or {}))
        response.raise_for_status()
        return response.content.decode("utf-8", errors="replace"), str(response.url)


def _strip_tags(value: str) -> str:
    return _text(html_lib.unescape(re.sub(r"<[^>]+>", " ", value or "")))


def _resolve_reference_slug_from_document(player_name: str, document: str) -> str:
    candidates: dict[str, dict[str, Any]] = {}
    for match in re.finditer(
        r"<a[^>]+href=[\"'](/players/[a-z]/([a-z0-9]+)\.html)[\"'][^>]*>(.*?)</a>",
        document or "",
        flags=re.I | re.S,
    ):
        label = re.sub(r"\s*\(\d{4}-\d{4}\)\s*$", "", _strip_tags(match.group(3)))
        key = _norm(label)
        if key and key not in candidates:
            candidates[key] = {"player_name": label, "slug": match.group(2).casefold()}
    matched = _match_reference_identity(player_name, candidates)
    return _text((matched or {}).get("slug")).casefold()


def _resolve_reference_slug(player_name: str) -> str:
    document, final_url = _get_text(REFERENCE_SEARCH, params={"search": player_name})
    direct = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", final_url, flags=re.I)
    if direct:
        return direct.group(1).casefold()
    return _resolve_reference_slug_from_document(player_name, document)


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


def _parse_reference_per_game_index(document: str) -> dict[str, dict[str, Any]]:
    """Parse one Basketball-Reference league per-game table into player identities.

    This is deliberately a bulk parser: one league page can identify hundreds of
    players without a search request per player. Season averages are retained as
    verified context, never converted into fake game rows.
    """
    rows: dict[str, dict[str, Any]] = {}
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", document or "", flags=re.I | re.S):
        cells: dict[str, str] = {}
        raw_cells: dict[str, str] = {}
        for stat, body in re.findall(
            r"<(?:td|th)\b[^>]*data-stat=[\"']([^\"']+)[\"'][^>]*>(.*?)</(?:td|th)>",
            row_html,
            flags=re.I | re.S,
        ):
            raw_cells[stat] = body
            cells[stat] = _strip_tags(body)
        name = _text(cells.get("name_display") or cells.get("player"))
        name_body = raw_cells.get("name_display") or raw_cells.get("player") or ""
        slug_match = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", name_body, flags=re.I)
        slug = slug_match.group(1).casefold() if slug_match else ""
        if not name or not slug:
            continue
        points = _num(cells.get("pts_per_g"))
        rebounds = _num(cells.get("trb_per_g"))
        assists = _num(cells.get("ast_per_g"))
        pra = None if any(value is None for value in (points, rebounds, assists)) else round(float(points) + float(rebounds) + float(assists), 3)
        baseline = {
            "games": int(float(cells["games"])) if _num(cells.get("games")) is not None else None,
            "minutes": _num(cells.get("mp_per_g")),
            "points": points,
            "rebounds": rebounds,
            "assists": assists,
            "pra": pra,
        }
        rows[_norm(name)] = {
            "player_name": name,
            "team": _text(cells.get("team_name_abbr")).upper(),
            "position": _text(cells.get("pos")),
            "provider_ids": {"basketball_reference": slug},
            "headshot": REFERENCE_HEADSHOT_TEMPLATE.format(slug=slug),
            "current_games": [],
            "prior_games": [],
            "stats_source": "Basketball-Reference identity index",
            "season_baseline": baseline,
        }
    return rows


def _reference_identity_profiles(slate_date: date, names: Sequence[str]) -> dict[str, Any]:
    wanted = {_norm(name) for name in names if _norm(name)}
    resolved: dict[str, dict[str, Any]] = {}
    attempts: list[str] = []
    end_year = _season_end_year(slate_date)
    for season in (end_year, end_year - 1):
        if wanted and wanted.issubset(resolved):
            break
        try:
            document, _ = _get_text(f"{REFERENCE_ROOT}/leagues/NBA_{season}_per_game.html", timeout=10.0)
            attempts.append(f"NBA_{season}:OK")
        except Exception as exc:
            attempts.append(f"NBA_{season}:{type(exc).__name__}")
            continue
        parsed = _parse_reference_per_game_index(document)
        for name in names:
            key = _norm(name)
            if not key or key in resolved:
                continue
            matched = _match_reference_identity(name, parsed)
            if matched:
                matched["identity_season"] = season
                resolved[key] = matched
    status = "HEALTHY" if wanted and len(resolved) == len(wanted) else "DEGRADED"
    return {
        "status": status,
        "diagnostic_state": f"BULK_RESOLVED_{len(resolved)}_OF_{len(wanted)}:" + ",".join(attempts),
        "profiles": resolved,
    }


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


def _reference_search_identity_profiles(slate_date: date, names: Sequence[str]) -> dict[str, Any]:
    del slate_date
    requested = list(names)[:REFERENCE_IDENTITY_SEARCH_BUDGET]
    rows: dict[str, dict[str, Any]] = {}
    rate_limited = False
    with httpx.Client(headers=REFERENCE_HEADERS, timeout=httpx.Timeout(8.0, connect=3.0), follow_redirects=True) as client:
        for name in requested:
            try:
                response = client.get(REFERENCE_SEARCH, params={"search": name})
                if response.status_code == 429:
                    rate_limited = True
                    break
                response.raise_for_status()
                document = response.content.decode("utf-8", errors="replace")
                slug = _resolve_reference_slug_from_document(name, document)
                if not slug:
                    continue
                profile_response = client.get(f"{REFERENCE_ROOT}/players/{slug[0]}/{slug}.html")
                if profile_response.status_code == 429:
                    rate_limited = True
                    break
                profile_response.raise_for_status()
                profile_html = profile_response.content.decode("utf-8", errors="replace")
                team, position, _headshot = _profile_meta(profile_html, slug)
                rows[_norm(name)] = {
                    "player_name": name,
                    "team": team,
                    "position": position,
                    "provider_ids": {"basketball_reference": slug},
                    "headshot": REFERENCE_HEADSHOT_TEMPLATE.format(slug=slug),
                    "current_games": [],
                    "prior_games": [],
                    "stats_source": "Basketball-Reference player identity",
                }
            except Exception:
                continue
            time.sleep(0.12)
    detail = f"SEARCH_RESOLVED_{len(rows)}_OF_{len(requested)}"
    if rate_limited:
        detail += ":RATE_LIMITED_STOP"
    return {
        "status": "HEALTHY" if requested and len(rows) == len(requested) else "DEGRADED",
        "diagnostic_state": detail,
        "profiles": rows,
    }


def _reference_player_from_identity(player_name: str, slate_date: date, seed: Mapping[str, Any] | None) -> dict[str, Any] | None:
    provider_ids = dict((seed or {}).get("provider_ids") or {})
    slug = _text(provider_ids.get("basketball_reference")).casefold()
    if not slug:
        return _reference_player(player_name, slate_date)
    letter = slug[0]
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
    out = dict(seed or {})
    out.update({
        "player_name": player_name,
        "provider_ids": {**provider_ids, "basketball_reference": slug},
        "current_games": current_games,
        "prior_games": prior_games,
        "stats_source": "Basketball-Reference",
    })
    return out


def _reference_profiles(
    slate_date: date,
    names: Sequence[str],
    *,
    seed_profiles: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    seeds = seed_profiles or {}
    requested = list(names)[:REFERENCE_HISTORY_BUDGET]
    if requested:
        with ThreadPoolExecutor(max_workers=min(2, len(requested))) as pool:
            jobs = {
                pool.submit(_reference_player_from_identity, name, slate_date, seeds.get(_norm(name))): name
                for name in requested
            }
            for future in as_completed(jobs):
                name = jobs[future]
                try:
                    row = future.result()
                except Exception:
                    row = None
                if row:
                    rows[_norm(name)] = row
    return {
        "status": "HEALTHY" if rows and len(rows) == len(requested) else "DEGRADED",
        "diagnostic_state": f"HISTORY_RESOLVED_{len(rows)}_OF_{len(requested)}_BUDGET_{REFERENCE_HISTORY_BUDGET}",
        "profiles": rows,
    }


def _merge_identity_rows(
    profiles: dict[str, dict[str, Any]],
    requested: Sequence[str],
    raw_rows: Mapping[str, Mapping[str, Any]],
) -> int:
    merged = 0
    for name in requested:
        key = _norm(name)
        row = raw_rows.get(key)
        if not isinstance(row, Mapping):
            continue
        normalized = _normalize_profile(name, row)
        existing = profiles.get(key)
        if existing is None:
            profiles[key] = normalized
            merged += 1
            continue
        if _history_ok(existing):
            continue
        combined = dict(normalized)
        for field in ("team", "position", "headshot", "stats_source", "season_baseline"):
            if existing.get(field):
                combined[field] = existing[field]
        combined["provider_ids"] = {**dict(normalized.get("provider_ids") or {}), **dict(existing.get("provider_ids") or {})}
        profiles[key] = _normalize_profile(name, combined)
        merged += 1
    return merged


def _merge_provider_rows(
    profiles: dict[str, dict[str, Any]],
    requested: Sequence[str],
    raw_rows: Mapping[str, Mapping[str, Any]],
) -> int:
    merged = 0
    for name in requested:
        key = _norm(name)
        row = raw_rows.get(key)
        if not isinstance(row, Mapping) or not _history_ok(row):
            continue
        existing = profiles.get(key) or {}
        combined = dict(existing)
        combined.update(dict(row))
        combined["provider_ids"] = {**dict(existing.get("provider_ids") or {}), **dict(row.get("provider_ids") or {})}
        for field in ("team", "position", "headshot", "season_baseline"):
            if not combined.get(field) and existing.get(field):
                combined[field] = existing[field]
        profiles[key] = _normalize_profile(name, combined)
        merged += 1
    return merged


def _parse_cbs_roster_html(document: str, team_code: str) -> dict[str, dict[str, Any]]:
    team = _text(team_code).upper()
    rows: dict[str, dict[str, Any]] = {}
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", document or "", flags=re.I | re.S):
        long = re.search(r'CellPlayerName--long.*?<a[^>]+href="/nba/players/(\d+)/[^\"]+/"[^>]*>(.*?)</a>', row_html, flags=re.I | re.S)
        if long is None:
            long = re.search(r'<a[^>]+href="/nba/players/(\d+)/[^\"]+/"[^>]*>(.*?)</a>', row_html, flags=re.I | re.S)
        if long is None:
            continue
        provider_id = _text(long.group(1))
        player_name = _strip_tags(long.group(2))
        if not provider_id or not player_name:
            continue
        cells = [_strip_tags(cell) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.I | re.S)]
        position = cells[2] if len(cells) >= 3 else ""
        rows[_norm(player_name)] = {
            "player_name": player_name,
            "team": team,
            "position": position,
            "provider_ids": {"cbs_sports": provider_id},
            "headshot": f"https://sportshub.cbsistatic.com/i/sports/player/headshot/{provider_id}.png?width=160",
            "current_games": [],
            "prior_games": [],
            "stats_source": "CBS Sports roster verification",
        }
    return rows


def _cbs_roster_profiles(team_code: str) -> dict[str, dict[str, Any]]:
    team = _text(team_code).upper()
    route = CBS_TEAM_ROSTERS.get(team)
    if route is None:
        return {}
    cbs_code, slug = route
    document, _ = _get_text(
        f"{CBS_ROOT}/nba/teams/{cbs_code}/{slug}/roster/",
        timeout=8.0,
        headers=CBS_HEADERS,
    )
    return _parse_cbs_roster_html(document, team)


def collect_nba_pra_player_context(
    slate_date: date,
    player_names: Sequence[str],
    *,
    team_codes: Sequence[str] | None = None,
    official_loader: Callable[[date, Sequence[str]], Any] | None = None,
    licensed_loaders: Sequence[Any] | None = None,
    basketball_reference_index_loader: Callable[[date, Sequence[str]], Any] | None = None,
    basketball_reference_loader: Callable[[date, Sequence[str]], Any] | None = None,
    cbs_roster_loader: Callable[[str], Any] | None = None,
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

    missing_history = [name for name in names if not _history_ok(profiles.get(_norm(name)))]
    licensed = list(licensed_loaders or [])
    if not licensed:
        health["sportradar"] = _health("UNAVAILABLE", "ADAPTER_NOT_CONFIGURED", False)
        health["sportsdataio"] = _health("UNAVAILABLE", "ADAPTER_NOT_CONFIGURED", False)
    for index, entry in enumerate(licensed):
        if not missing_history:
            break
        if isinstance(entry, tuple) and len(entry) == 2:
            provider_name, loader = str(entry[0]), entry[1]
        else:
            loader = entry
            provider_name = getattr(loader, "__name__", None) or f"licensed_{index + 1}"
        try:
            status, rows, detail = _coerce_provider_payload(loader(slate_date, missing_history))
            _merge_provider_rows(profiles, missing_history, rows)
            health[provider_name] = _health(status, detail, True)
        except Exception as exc:
            health[provider_name] = _health("DEGRADED", type(exc).__name__, True)
        missing_history = [name for name in names if not _history_ok(profiles.get(_norm(name)))]

    identity_missing = [name for name in names if _norm(name) not in profiles or profiles[_norm(name)].get("data_state") == "DATA_UNAVAILABLE"]
    identity_reference = basketball_reference_index_loader
    if identity_reference is None and basketball_reference_loader is None:
        identity_reference = _reference_identity_profiles
    if identity_missing and identity_reference is not None:
        try:
            status, rows, detail = _coerce_provider_payload(identity_reference(slate_date, identity_missing))
            _merge_identity_rows(profiles, identity_missing, rows)
            health["basketball_reference_identity"] = _health(status, detail, True)
        except Exception as exc:
            health["basketball_reference_identity"] = _health("DEGRADED", type(exc).__name__, True)
    else:
        health["basketball_reference_identity"] = _health("HEALTHY", "NOT_NEEDED", False)

    unresolved_identity = [name for name in names if _norm(name) not in profiles or profiles[_norm(name)].get("data_state") == "DATA_UNAVAILABLE"]
    if unresolved_identity and not team_codes and basketball_reference_index_loader is None and basketball_reference_loader is None:
        try:
            status, rows, detail = _coerce_provider_payload(_reference_search_identity_profiles(slate_date, unresolved_identity))
            _merge_identity_rows(profiles, unresolved_identity, rows)
            health["basketball_reference_identity_search"] = _health(status, detail, True)
        except Exception as exc:
            health["basketball_reference_identity_search"] = _health("DEGRADED", type(exc).__name__, True)
    else:
        health["basketball_reference_identity_search"] = _health("HEALTHY", "NOT_NEEDED", False)

    unresolved_identity = [name for name in names if _norm(name) not in profiles or profiles[_norm(name)].get("data_state") == "DATA_UNAVAILABLE"]
    codes = []
    seen_codes: set[str] = set()
    for raw_code in team_codes or []:
        code = _text(raw_code).upper()
        if code in CBS_TEAM_ROSTERS and code not in seen_codes:
            codes.append(code)
            seen_codes.add(code)
    cbs_loader = cbs_roster_loader or _cbs_roster_profiles
    cbs_rows: dict[str, dict[str, Any]] = {}
    cbs_attempted = False
    if unresolved_identity and codes:
        for code in codes:
            try:
                raw_rows = cbs_loader(code) or {}
                cbs_attempted = True
                if isinstance(raw_rows, Mapping):
                    for key, row in raw_rows.items():
                        if isinstance(row, Mapping):
                            cbs_rows[str(key)] = dict(row)
            except Exception:
                cbs_attempted = True
                continue
        matched_rows: dict[str, dict[str, Any]] = {}
        for name in unresolved_identity:
            matched = _match_reference_identity(name, cbs_rows)
            if matched is not None:
                matched_rows[_norm(name)] = matched
        _merge_identity_rows(profiles, unresolved_identity, matched_rows)
        unresolved_after_cbs = [name for name in unresolved_identity if _norm(name) not in profiles or profiles[_norm(name)].get("data_state") == "DATA_UNAVAILABLE"]
        status = "HEALTHY" if not unresolved_after_cbs else "DEGRADED"
        health["cbs_sports_identity"] = _health(status, f"RESOLVED_{len(unresolved_identity)-len(unresolved_after_cbs)}_OF_{len(unresolved_identity)}", cbs_attempted)
    else:
        health["cbs_sports_identity"] = _health("HEALTHY", "NOT_NEEDED", False)

    missing_history = [name for name in names if not _history_ok(profiles.get(_norm(name)))]
    bounded_history = missing_history[:REFERENCE_HISTORY_BUDGET]
    reference_identity_degraded = (health.get("basketball_reference_identity") or {}).get("status") == "DEGRADED"
    history_allowed = basketball_reference_loader is not None or not reference_identity_degraded
    if bounded_history and history_allowed:
        try:
            if basketball_reference_loader is not None:
                raw_value = basketball_reference_loader(slate_date, bounded_history)
            else:
                raw_value = _reference_profiles(slate_date, bounded_history, seed_profiles=profiles)
            status, rows, detail = _coerce_provider_payload(raw_value)
            _merge_provider_rows(profiles, bounded_history, rows)
            health["basketball_reference"] = _health(status, detail, True)
        except Exception as exc:
            health["basketball_reference"] = _health("DEGRADED", type(exc).__name__, True)
    else:
        detail = "SKIPPED_AFTER_IDENTITY_DEGRADED" if bounded_history and not history_allowed else "NOT_NEEDED"
        health["basketball_reference"] = _health("UNAVAILABLE" if detail != "NOT_NEEDED" else "HEALTHY", detail, False)

    for name in names:
        key = _norm(name)
        if key in profiles:
            profiles[key] = _normalize_profile(name, profiles[key])
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
    identified = sum(1 for row in profiles.values() if row.get("data_state") in {"VERIFIED", "IDENTITY_ONLY"})
    verification = "VERIFIED" if names and verified == len(names) else "PARTIAL" if identified else "DATA_UNAVAILABLE"
    return {
        "schema_version": "KYRE_NBA_PLAYER_CONTEXT_V1",
        "date": slate_date.isoformat(),
        "verification": verification,
        "profiles": profiles,
        "provider_health": health,
        "verified_players": verified,
        "identified_players": identified,
        "requested_players": len(names),
        "history_budget": REFERENCE_HISTORY_BUDGET,
        "fabrication": False,
    }


class NbaPraPlayerContextRequest(BaseModel):
    date: date
    player_names: list[str] = Field(min_length=1, max_length=200)
    team_codes: list[str] = Field(default_factory=list, max_length=30)


@router.post("")
def player_context(request: NbaPraPlayerContextRequest) -> dict[str, Any]:
    return collect_nba_pra_player_context(request.date, request.player_names, team_codes=request.team_codes)
