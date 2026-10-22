"""Verified NCAA + official-roster identity enrichment for CFB Top Picks V4.

Enrichment only: rankings, probabilities, sportsbook lines and selections are
owned by frozen V3 and are never modified here.
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


def _fresh(at: datetime | None, ttl: int) -> bool:
    return bool(at and datetime.now(timezone.utc) - at < timedelta(seconds=ttl))


def _fetch_text(url: str, timeout: float = 15.0) -> tuple[str, dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return response.text, {"url": str(response.url), "http": response.status_code, "transport": "requests", "status": "VERIFIED"}
    except Exception as first:
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - approved public source
                return response.read().decode("utf-8", errors="replace"), {"url": str(response.geturl()), "http": int(response.status), "transport": "urllib", "status": "VERIFIED"}
        except Exception as second:
            return "", {"url": url, "http": None, "transport": "failed", "status": "UNAVAILABLE", "error": f"{type(first).__name__}/{type(second).__name__}"}


def parse_ncaa_winning_percentage_html(source: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", source or "", flags=re.I | re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        if len(cells) < 6:
            continue
        school = re.search(r"href=[\"'](?:https?://www\.ncaa\.com)?/schools/([^\"'/?#]+)[\"'][^>]*>(.*?)</a>", cells[1], flags=re.I | re.S)
        if not school:
            continue
        slug = _clean(school.group(1)).strip("/").casefold()
        name = _strip_tags(school.group(2))
        try:
            wins, losses, ties = (int(_strip_tags(cells[i])) for i in (2, 3, 4))
        except (TypeError, ValueError):
            continue
        if not slug or not name:
            continue
        out[slug] = {
            "team_name": name,
            "school_slug": slug,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "record_text": f"{wins}-{losses}" + (f"-{ties}" if ties else ""),
            "record_status": "VERIFIED",
            "logo_url": f"{NCAA_LOGO_DARK_BASE}{slug}.svg",
            "school_url": f"{NCAA_SCHOOL_BASE}{slug}",
            "source": "NCAA Winning Percentage",
        }
    return out


def load_ncaa_team_identity(*, force: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not force and _fresh(_team_cache.get("at"), IDENTITY_TTL_SECONDS):
        value = dict(_team_cache.get("value") or {})
        return value, {"source": "NCAA Winning Percentage", "cache": "HIT", "teams": len(value)}
    text, fetch = _fetch_text(NCAA_WINNING_PERCENTAGE_URL)
    value = parse_ncaa_winning_percentage_html(text) if text else {}
    if value:
        _team_cache.update(at=datetime.now(timezone.utc), value=dict(value))
    return value, {"source": "NCAA Winning Percentage", "cache": "MISS", "teams": len(value), "fetch": fetch}


def find_team_identity(team_name: Any, team_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    wanted = _norm(team_name)
    if not wanted:
        return None
    matches = [dict(row) for row in team_index.values() if _norm(row.get("team_name")) == wanted]
    return matches[0] if len(matches) == 1 else None


def parse_ncaa_official_site(source: str) -> str | None:
    text = source or ""
    marker = re.search(r"class=[\"'][^\"']*school-links[^\"']*[\"']", text, flags=re.I)
    block = text[marker.start():marker.start() + 12000] if marker else text
    social = ("twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com", "tiktok.com")
    links = list(re.finditer(r"<a\b[^>]*href=[\"'](https?://[^\"']+)[\"'][^>]*>(.*?)</a>", block, flags=re.I | re.S))
    for match in links:
        href = html_lib.unescape(match.group(1)).strip().rstrip("/")
        if "icon-web" in match.group(2) and href:
            return href
    for match in links:
        href = html_lib.unescape(match.group(1)).strip().rstrip("/")
        lowered = href.casefold()
        if href and "ncaa.com" not in lowered and not any(host in lowered for host in social):
            return href
    return None


def _without_sr_only(segment: str) -> str:
    return re.sub(r"<span\b[^>]*class=[\"'][^\"']*sr-only[^\"']*[\"'][^>]*>.*?</span>", "", segment, flags=re.I | re.S)


def _roster_value(segment: str, token: str) -> str | None:
    clean_segment = _without_sr_only(segment)
    match = re.search(rf"<[^>]+data-test-id=[\"'][^\"']*{re.escape(token)}[^\"']*[\"'][^>]*>(.*?)</[^>]+>", clean_segment, flags=re.I | re.S)
    value = _strip_tags(match.group(1)) if match else ""
    return value or None


def parse_official_roster_html(source: str, official_site: str) -> dict[str, dict[str, Any]]:
    text = source or ""
    out: dict[str, dict[str, Any]] = {}
    pattern = r"<a\b([^>]*)data-test-id=[\"']s-person-details__personal-single-line-person-link[\"']([^>]*)>(.*?)</a>"
    for match in re.finditer(pattern, text, flags=re.I | re.S):
        attrs = f"{match.group(1)} {match.group(2)}"
        player_name = _strip_tags(match.group(3))
        href_match = re.search(r"href=[\"']([^\"']+)[\"']", attrs, flags=re.I)
        if not player_name or not href_match:
            continue
        profile_path = html_lib.unescape(href_match.group(1)).strip()
        id_match = re.search(r"/sports/football/roster/[^/?#]+/(\d+)(?:[/?#]|$)", profile_path, flags=re.I)
        start = text.rfind("<li", 0, match.start())
        end = text.find("</li>", match.end())
        start = start if start >= 0 else max(0, match.start() - 5000)
        end = end + 5 if end >= 0 else min(len(text), match.end() + 9000)
        segment = text[start:end]
        aria = re.search(rf"aria-label=[\"'][^\"']*{re.escape(player_name)}[^\"']*jersey number\s+([^\s\"']+)[^\"']*full bio[\"']", segment, flags=re.I)
        image = re.search(r"<img\b[^>]*data-test-id=[\"']s-image-resized__img[\"'][^>]*src=[\"']([^\"']+)[\"']", segment, flags=re.I | re.S)
        if not image:
            image = re.search(r"<img\b[^>]*src=[\"']([^\"']+)[\"'][^>]*data-test-id=[\"']s-image-resized__img[\"']", segment, flags=re.I | re.S)
        key = _norm(player_name)
        if not key:
            continue
        out[key] = {
            "player_name": player_name,
            "official_roster_id": id_match.group(1) if id_match else None,
            "headshot_url": html_lib.unescape(image.group(1)).strip() if image else None,
            "position": _roster_value(segment, "person-position-short"),
            "jersey_number": _clean(aria.group(1)) if aria else None,
            "class_year": _roster_value(segment, "person-season"),
            "profile_url": urljoin(official_site.rstrip("/") + "/", profile_path.lstrip("/")),
            "identity_source": "Official team roster",
        }
    return out


def _discover_roster_url(site: str, source: str) -> str:
    for raw in re.findall(r"href=[\"']([^\"']*/sports/football/roster[^\"']*)[\"']", source or "", flags=re.I):
        value = html_lib.unescape(raw).strip()
        if value:
            return urljoin(site.rstrip("/") + "/", value.lstrip("/"))
    return site.rstrip("/") + "/sports/football/roster"


def load_official_roster(team: Mapping[str, Any], *, force: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    slug = _clean(team.get("school_slug")).casefold()
    if not slug:
        return {}, {"status": "UNAVAILABLE", "reason": "NCAA_SCHOOL_SLUG_MISSING"}
    cached = _roster_cache.get(slug)
    if cached and not force and _fresh(cached.get("at"), ROSTER_TTL_SECONDS):
        players = dict(cached.get("players") or {})
        return players, {"status": "VERIFIED", "cache": "HIT", "players": len(players), "team_slug": slug}
    school = _school_cache.get(slug)
    if school and not force and _fresh(school.get("at"), ROSTER_TTL_SECONDS):
        official_site, school_diag = school.get("site"), dict(school.get("diag") or {})
    else:
        school_html, school_fetch = _fetch_text(_clean(team.get("school_url")) or f"{NCAA_SCHOOL_BASE}{slug}")
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
        site_html, _ = _fetch_text(official_site)
        discovered = _discover_roster_url(official_site, site_html)
        if discovered != default_url:
            roster_html, roster_fetch = _fetch_text(discovered)
            roster_url = discovered
            players = parse_official_roster_html(roster_html, official_site) if roster_html else {}
    if players:
        _roster_cache[slug] = {"at": datetime.now(timezone.utc), "players": dict(players)}
    return players, {"status": "VERIFIED" if players else "UNAVAILABLE", "team_slug": slug, "official_site": official_site, "roster_url": roster_url, "players": len(players), "roster_fetch": roster_fetch, **school_diag}


def resolve_player_identity(player_name: Any, away_team: Mapping[str, Any] | None, home_team: Mapping[str, Any] | None, roster_index: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    key = _norm(player_name)
    if not key:
        return {"identity_status": "NOT_AVAILABLE", "player_id_display": "ID unavailable"}
    matches: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for side, team in (("away", away_team), ("home", home_team)):
        if not team:
            continue
        slug = _clean(team.get("school_slug") or team.get("slug")).casefold()
        player = (roster_index.get(slug) or {}).get(key)
        if player:
            matches.append((dict(team), dict(player), side))
    if len(matches) != 1:
        return {"identity_status": "CONFLICTING" if len(matches) > 1 else "NOT_AVAILABLE", "player_id_display": "ID unavailable"}
    team, player, side = matches[0]
    opponent = home_team if side == "away" else away_team
    player_id = _clean(player.get("official_roster_id")) or None
    return {
        "identity_status": "VERIFIED",
        "player_team": _clean(team.get("team_name") or team.get("name")) or None,
        "player_team_slug": _clean(team.get("school_slug") or team.get("slug")) or None,
        "team_logo": _clean(team.get("logo_url")) or None,
        "opponent": _clean((opponent or {}).get("team_name") or (opponent or {}).get("name")) or None,
        "official_roster_id": player_id,
        "player_id_display": player_id or "ID unavailable",
        "player_headshot": _clean(player.get("headshot_url")) or None,
        "position": _clean(player.get("position")) or None,
        "jersey_number": _clean(player.get("jersey_number")) or None,
        "class_year": _clean(player.get("class_year")) or None,
        "official_profile_url": _clean(player.get("profile_url")) or None,
        "identity_source": "Official team roster",
    }


__all__ = ["find_team_identity", "load_ncaa_team_identity", "load_official_roster", "parse_ncaa_official_site", "parse_ncaa_winning_percentage_html", "parse_official_roster_html", "resolve_player_identity"]
