"""Verified CFB Page 1 identity enrichment for Top Picks V4.

This module is enrichment-only. It never changes rankings, probabilities,
projections, sportsbook lines, or selection logic.

Approved sources used here:
- NCAA current FBS Winning Percentage table: current W/L/T + canonical school
  slug + official NCAA logo identity.
- NCAA school page: official athletics website discovery.
- Official athletics football roster: current player team, roster/profile ID,
  headshot, position, jersey number, and class/year when published.

No SGO. No ESPN. No ESPN BET.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import html as html_lib
import re
from typing import Any, Mapping
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import requests

NCAA_WINNING_PERCENTAGE_URL = "https://www.ncaa.com/stats/football/fbs/current/team/742"
NCAA_SCHOOL_BASE = "https://www.ncaa.com/schools/"
NCAA_LOGO_DARK_BASE = "https://www.ncaa.com/sites/default/files/images/logos/schools/bgd/"
USER_AGENT = "KyreSportsAI/1.0"
IDENTITY_TTL_SECONDS = 180
ROSTER_TTL_SECONDS = 300

_team_cache: dict[str, Any] = {"at": None, "value": {}}
_roster_cache: dict[str, dict[str, Any]] = {}
_school_cache: dict[str, dict[str, Any]] = {}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(str(value or ""))).strip()


def _strip_tags(value: Any) -> str:
    return _clean(re.sub(r"<[^>]+>", " ", str(value or "")))


def _norm(value: Any) -> str:
    text = _clean(value).casefold().replace("&", " and ")
    text = re.sub(r"\bst\.?\b", " state ", text)
    text = re.sub(r"\buniv(?:ersity)?\b", " ", text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _cache_fresh(at: datetime | None, ttl_seconds: int) -> bool:
    if at is None:
        return False
    return datetime.now(timezone.utc) - at < timedelta(seconds=ttl_seconds)


def _fetch_text(url: str, *, timeout: float = 15.0) -> tuple[str, dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return response.text, {
            "url": str(response.url),
            "http": int(response.status_code),
            "transport": "requests",
            "status": "VERIFIED",
        }
    except Exception as first_error:
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - approved public source
                body = response.read().decode("utf-8", errors="replace")
                return body, {
                    "url": str(response.geturl()),
                    "http": int(response.status),
                    "transport": "urllib",
                    "status": "VERIFIED",
                }
        except Exception as second_error:
            return "", {
                "url": url,
                "http": None,
                "transport": "failed",
                "status": "UNAVAILABLE",
                "error": f"{type(first_error).__name__}/{type(second_error).__name__}",
            }


def parse_ncaa_winning_percentage_html(source: str) -> dict[str, dict[str, Any]]:
    """Parse NCAA's current Winning Percentage table into canonical teams."""
    out: dict[str, dict[str, Any]] = {}
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", source or "", flags=re.I | re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.I | re.S)
        if len(cells) < 6:
            continue
        team_cell = cells[1]
        school = re.search(
            r"href=[\"'](?:https?://www\.ncaa\.com)?/schools/([^\"'/?#]+)[\"'][^>]*>(.*?)</a>",
            team_cell,
            flags=re.I | re.S,
        )
        if not school:
            continue
        slug = _clean(school.group(1)).strip("/").casefold()
        team_name = _strip_tags(school.group(2))
        if not slug or not team_name:
            continue
        try:
            wins = int(_strip_tags(cells[2]))
            losses = int(_strip_tags(cells[3]))
            ties = int(_strip_tags(cells[4]))
        except (TypeError, ValueError):
            continue
        record_text = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
        out[slug] = {
            "team_name": team_name,
            "school_slug": slug,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "record_text": record_text,
            "record_status": "VERIFIED",
            "logo_url": f"{NCAA_LOGO_DARK_BASE}{slug}.svg",
            "school_url": f"{NCAA_SCHOOL_BASE}{slug}",
            "source": "NCAA Winning Percentage",
        }
    return out


def load_ncaa_team_identity(*, force: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    cached_at = _team_cache.get("at")
    if not force and _cache_fresh(cached_at, IDENTITY_TTL_SECONDS):
        value = _team_cache.get("value") or {}
        return dict(value), {"source": "NCAA Winning Percentage", "cache": "HIT", "teams": len(value)}
    text, fetch = _fetch_text(NCAA_WINNING_PERCENTAGE_URL)
    value = parse_ncaa_winning_percentage_html(text) if text else {}
    if value:
        _team_cache["at"] = datetime.now(timezone.utc)
        _team_cache["value"] = dict(value)
    return value, {
        "source": "NCAA Winning Percentage",
        "cache": "MISS",
        "teams": len(value),
        "fetch": fetch,
    }


def find_team_identity(team_name: Any, team_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    """Resolve a team only when exactly one NCAA identity matches."""
    wanted = _norm(team_name)
    if not wanted:
        return None
    exact: list[dict[str, Any]] = []
    for raw in team_index.values():
        row = dict(raw)
        if _norm(row.get("team_name")) == wanted:
            exact.append(row)
    if len(exact) == 1:
        return exact[0]
    return None


def parse_ncaa_official_site(source: str) -> str | None:
    """Read the official athletics website from NCAA's school-links block."""
    text = source or ""
    block_match = re.search(r"<div\b[^>]*class=[\"'][^\"']*school-links[^\"']*[\"'][^>]*>(.*?)</div>\s*</div>", text, flags=re.I | re.S)
    block = block_match.group(1) if block_match else text
    for match in re.finditer(r"<a\b[^>]*href=[\"'](https?://[^\"']+)[\"'][^>]*>(.*?)</a>", block, flags=re.I | re.S):
        href = html_lib.unescape(match.group(1)).strip()
        body = match.group(2)
        if "icon-web" in body or re.search(r"\b(?:athletics|sports)\b", _strip_tags(body), flags=re.I):
            return href.rstrip("/")
    # NCAA school pages put the official site first in school-links. This
    # fallback stays inside that block and excludes social networks.
    social = ("twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com", "tiktok.com")
    for href in re.findall(r"href=[\"'](https?://[^\"']+)[\"']", block, flags=re.I):
        clean = html_lib.unescape(href).strip().rstrip("/")
        if clean and not any(host in clean.casefold() for host in social) and "ncaa.com" not in clean.casefold():
            return clean
    return None


def _extract_roster_value(segment: str, token: str) -> str | None:
    match = re.search(
        rf"<[^>]+data-test-id=[\"'][^\"']*{re.escape(token)}[^\"']*[\"'][^>]*>(.*?)</[^>]+>",
        segment,
        flags=re.I | re.S,
    )
    if not match:
        return None
    value = _strip_tags(match.group(1))
    value = re.sub(r"^(?:Position|Academic Year|Class|Season)\s+", "", value, flags=re.I).strip()
    return value or None


def parse_official_roster_html(source: str, official_site: str) -> dict[str, dict[str, Any]]:
    """Parse current Sidearm-style official roster cards without JS/OCR."""
    text = source or ""
    out: dict[str, dict[str, Any]] = {}
    player_links = list(re.finditer(
        r"<a\b([^>]*)data-test-id=[\"']s-person-details__personal-single-line-person-link[\"']([^>]*)>(.*?)</a>",
        text,
        flags=re.I | re.S,
    ))
    for match in player_links:
        attrs = f"{match.group(1)} {match.group(2)}"
        player_name = _strip_tags(match.group(3))
        href_match = re.search(r"href=[\"']([^\"']+)[\"']", attrs, flags=re.I)
        if not player_name or not href_match:
            continue
        profile_path = html_lib.unescape(href_match.group(1)).strip()
        id_match = re.search(r"/sports/football/roster/[^/?#]+/(\d+)(?:[/?#]|$)", profile_path, flags=re.I)
        official_roster_id = id_match.group(1) if id_match else None

        start = text.rfind("<li", 0, match.start())
        end = text.find("</li>", match.end())
        if start < 0:
            start = max(0, match.start() - 5000)
        if end < 0:
            end = min(len(text), match.end() + 9000)
        else:
            end += len("</li>")
        segment = text[start:end]

        aria = re.search(
            rf"aria-label=[\"'][^\"']*{re.escape(player_name)}[^\"']*jersey number\s+([^\s\"']+)[^\"']*full bio[\"']",
            segment,
            flags=re.I,
        )
        jersey = _clean(aria.group(1)) if aria else None
        position = _extract_roster_value(segment, "person-position-short")
        class_year = _extract_roster_value(segment, "person-season")

        headshot = None
        image = re.search(
            r"<img\b[^>]*data-test-id=[\"']s-image-resized__img[\"'][^>]*src=[\"']([^\"']+)[\"']",
            segment,
            flags=re.I | re.S,
        )
        if not image:
            image = re.search(
                r"<img\b[^>]*src=[\"']([^\"']+)[\"'][^>]*data-test-id=[\"']s-image-resized__img[\"']",
                segment,
                flags=re.I | re.S,
            )
        if image:
            headshot = html_lib.unescape(image.group(1)).strip()

        key = _norm(player_name)
        if not key:
            continue
        out[key] = {
            "player_name": player_name,
            "official_roster_id": official_roster_id,
            "headshot_url": headshot,
            "position": position,
            "jersey_number": jersey,
            "class_year": class_year,
            "profile_url": urljoin(official_site.rstrip("/") + "/", profile_path.lstrip("/")),
            "identity_source": "Official team roster",
        }
    return out


def _discover_roster_url(site: str, source: str) -> str:
    default = site.rstrip("/") + "/sports/football/roster"
    candidates = re.findall(r"href=[\"']([^\"']*/sports/football/roster[^\"']*)[\"']", source or "", flags=re.I)
    for candidate in candidates:
        clean = html_lib.unescape(candidate).strip()
        if clean:
            return urljoin(site.rstrip("/") + "/", clean.lstrip("/"))
    return default


def load_official_roster(team: Mapping[str, Any], *, force: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    slug = _clean(team.get("school_slug")).casefold()
    if not slug:
        return {}, {"status": "UNAVAILABLE", "reason": "NCAA_SCHOOL_SLUG_MISSING"}
    cached = _roster_cache.get(slug)
    if cached and not force and _cache_fresh(cached.get("at"), ROSTER_TTL_SECONDS):
        players = cached.get("players") or {}
        return dict(players), {"status": "VERIFIED", "cache": "HIT", "players": len(players), "team_slug": slug}

    school = _school_cache.get(slug)
    if school and not force and _cache_fresh(school.get("at"), ROSTER_TTL_SECONDS):
        official_site = school.get("site")
        school_diag = school.get("diag") or {}
    else:
        school_url = _clean(team.get("school_url")) or f"{NCAA_SCHOOL_BASE}{slug}"
        school_html, school_fetch = _fetch_text(school_url)
        official_site = parse_ncaa_official_site(school_html) if school_html else None
        school_diag = {"school_fetch": school_fetch, "official_site": official_site}
        _school_cache[slug] = {"at": datetime.now(timezone.utc), "site": official_site, "diag": school_diag}

    if not official_site:
        return {}, {"status": "UNAVAILABLE", "reason": "OFFICIAL_ATHLETICS_SITE_NOT_FOUND", "team_slug": slug, **school_diag}

    default_url = official_site.rstrip("/") + "/sports/football/roster"
    roster_html, roster_fetch = _fetch_text(default_url)
    roster_url = default_url
    players = parse_official_roster_html(roster_html, official_site) if roster_html else {}

    if not players:
        site_html, _site_fetch = _fetch_text(official_site)
        discovered = _discover_roster_url(official_site, site_html)
        if discovered != default_url:
            roster_html, roster_fetch = _fetch_text(discovered)
            roster_url = discovered
            players = parse_official_roster_html(roster_html, official_site) if roster_html else {}

    if players:
        _roster_cache[slug] = {"at": datetime.now(timezone.utc), "players": dict(players)}
    return players, {
        "status": "VERIFIED" if players else "UNAVAILABLE",
        "team_slug": slug,
        "official_site": official_site,
        "roster_url": roster_url,
        "players": len(players),
        "roster_fetch": roster_fetch,
        **school_diag,
    }


def resolve_player_identity(
    player_name: Any,
    away_team: Mapping[str, Any] | None,
    home_team: Mapping[str, Any] | None,
    roster_index: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Resolve a selected prop player against only the verified game's teams."""
    key = _norm(player_name)
    if not key:
        return {"identity_status": "NOT_AVAILABLE", "player_id_display": "ID unavailable"}
    matches: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for side, team in (("away", away_team), ("home", home_team)):
        if not team:
            continue
        slug = _clean(team.get("school_slug")).casefold()
        player = (roster_index.get(slug) or {}).get(key)
        if player:
            matches.append((dict(team), dict(player), side))
    if len(matches) != 1:
        status = "CONFLICTING" if len(matches) > 1 else "NOT_AVAILABLE"
        return {"identity_status": status, "player_id_display": "ID unavailable"}

    team, player, side = matches[0]
    opponent = home_team if side == "away" else away_team
    player_id = _clean(player.get("official_roster_id")) or None
    return {
        "identity_status": "VERIFIED",
        "player_team": _clean(team.get("team_name")) or None,
        "player_team_slug": _clean(team.get("school_slug")) or None,
        "team_logo": _clean(team.get("logo_url")) or None,
        "opponent": _clean((opponent or {}).get("team_name")) or None,
        "official_roster_id": player_id,
        "player_id_display": player_id or "ID unavailable",
        "player_headshot": _clean(player.get("headshot_url")) or None,
        "position": _clean(player.get("position")) or None,
        "jersey_number": _clean(player.get("jersey_number")) or None,
        "class_year": _clean(player.get("class_year")) or None,
        "official_profile_url": _clean(player.get("profile_url")) or None,
        "identity_source": "Official team roster",
    }


__all__ = [
    "NCAA_LOGO_DARK_BASE",
    "NCAA_SCHOOL_BASE",
    "NCAA_WINNING_PERCENTAGE_URL",
    "find_team_identity",
    "load_ncaa_team_identity",
    "load_official_roster",
    "parse_ncaa_official_site",
    "parse_ncaa_winning_percentage_html",
    "parse_official_roster_html",
    "resolve_player_identity",
]
