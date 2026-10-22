"""Identity enrichment for CFB Top Picks Page 1.

NCAA owns team identity, official logos and current W-L records. Official school
athletics roster pages are queried only for the final selected player props and
only after NCAA game identity is known. No sportsbook/model math lives here.
"""
from __future__ import annotations

from functools import lru_cache
from html import unescape
import re
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

import requests

NCAA_WIN_PCT_URL = "https://www.ncaa.com/stats/football/fbs/current/team/742"
NCAA_SCHOOL_URL = "https://www.ncaa.com/schools/{slug}"
USER_AGENT = "KyreSportsAI/1.0"
TIMEOUT = 18


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _strip_tags(value: str) -> str:
    return _clean(re.sub(r"<[^>]+>", " ", value or ""))


def _norm(value: Any) -> str:
    text = _clean(value).casefold().replace("&", " and ")
    text = re.sub(r"\bstate\b", "st", text)
    text = re.sub(r"\bsaint\b", "st", text)
    text = re.sub(r"\buniversity\b", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _get(url: str) -> str:
    response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


@lru_cache(maxsize=1)
def load_ncaa_team_index() -> dict[str, dict[str, Any]]:
    """Return current FBS identity/record rows keyed by normalized name/slug."""
    pages: list[str] = []
    for suffix in ("", "/p2", "/p3"):
        try:
            pages.append(_get(NCAA_WIN_PCT_URL + suffix))
        except Exception:
            if not pages:
                return {}
            break

    index: dict[str, dict[str, Any]] = {}
    for html in pages:
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.I | re.S):
            school = re.search(
                r'href=["\']/schools/([^"\']+)["\'][^>]*class=["\']school["\'][^>]*>(.*?)</a>',
                row_html,
                flags=re.I | re.S,
            )
            if not school:
                continue
            slug = _clean(school.group(1))
            name = _strip_tags(school.group(2))
            cells = [_strip_tags(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.I | re.S)]
            if len(cells) < 6:
                continue
            try:
                wins, losses, ties = int(cells[-4]), int(cells[-3]), int(cells[-2])
            except (TypeError, ValueError):
                continue
            record = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
            logo_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', row_html, flags=re.I)
            logo = _clean(logo_match.group(1)) if logo_match else ""
            if logo.startswith("/"):
                logo = urljoin("https://www.ncaa.com", logo)
            info = {
                "team_name": name,
                "ncaa_school_slug": slug,
                "ncaa_team_id": slug,
                "record": record,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "logo": logo or f"https://www.ncaa.com/sites/default/files/images/logos/schools/bgl/{slug}.svg",
                "source": "NCAA Winning Percentage",
            }
            for key in {_norm(name), _norm(slug.replace("-", " "))}:
                if key:
                    index[key] = info
    return index


def lookup_team(team_name: Any, index: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any] | None:
    index = index or load_ncaa_team_index()
    key = _norm(team_name)
    if key in index:
        return dict(index[key])
    matches: list[Mapping[str, Any]] = []
    for candidate_key, info in index.items():
        if not candidate_key:
            continue
        if key == candidate_key or (len(key) >= 5 and len(candidate_key) >= 5 and (key in candidate_key or candidate_key in key)):
            matches.append(info)
    unique = {str(row.get("ncaa_school_slug")): row for row in matches}
    return dict(next(iter(unique.values()))) if len(unique) == 1 else None


@lru_cache(maxsize=256)
def official_athletics_base(ncaa_slug: str) -> str:
    """Resolve the NCAA-published official athletics website for a school."""
    try:
        html = _get(NCAA_SCHOOL_URL.format(slug=ncaa_slug))
    except Exception:
        return ""
    block_at = html.find('class="school-links"')
    if block_at < 0:
        block_at = html.find("class='school-links'")
    block = html[block_at : block_at + 12000] if block_at >= 0 else html
    for href in re.findall(r'href=["\'](https?://[^"\']+)["\']', block, flags=re.I):
        host = (urlparse(href).hostname or "").casefold()
        if not host or "ncaa.com" in host or "twitter.com" in host or "x.com" in host or "facebook.com" in host or "instagram.com" in host:
            continue
        return href.rstrip("/")
    return ""


def _extract_profile_id(href: str) -> str:
    match = re.search(r"/(\d+)(?:[/?#]|$)", href or "")
    return match.group(1) if match else ""


def _field_from_card(card: str, token: str) -> str:
    label = {"person-position-short": "Position", "person-season": "Academic Year"}.get(token, "")
    if label:
        match = re.search(rf'>{re.escape(label)}</span>\s*([^<]+)', card, flags=re.I | re.S)
        if match:
            return _clean(match.group(1))
    return ""


def _player_alias_match(requested: str, roster_name: str) -> bool:
    a = _norm(requested).split()
    b = _norm(roster_name).split()
    if not a or not b:
        return False
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    it = iter(large)
    return all(any(token == candidate for candidate in it) for token in small)


@lru_cache(maxsize=256)
def load_official_roster(ncaa_slug: str) -> dict[str, dict[str, Any]]:
    """Load one current official football roster and index exact player names."""
    base = official_athletics_base(ncaa_slug)
    if not base:
        return {}
    roster_url = base + "/sports/football/roster"
    try:
        html = _get(roster_url)
    except Exception:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    profile_re = re.compile(
        r'href=["\']([^"\']*/sports/football/roster/[^"\']+/\d+)["\'][^>]*>(.*?)</a>',
        flags=re.I | re.S,
    )
    for match in profile_re.finditer(html):
        href = unescape(match.group(1))
        name = _strip_tags(match.group(2))
        if not name or len(name.split()) < 2:
            continue
        key = _norm(name)
        if key in rows:
            continue
        start = max(0, html.rfind("<li", 0, match.start()))
        end = html.find("</li>", match.end())
        if end < 0:
            end = min(len(html), match.end() + 12000)
        card = html[start : end + 5]
        img_match = re.search(
            r'data-test-id=["\']s-image-resized__img["\'][^>]+(?:src|srcset)=["\']([^"\']+)',
            card,
            flags=re.I,
        )
        if not img_match:
            img_match = re.search(r'<img[^>]+(?:src|srcset)=["\']([^"\']+)["\']', card, flags=re.I)
        headshot = unescape(img_match.group(1)).split(" 1x")[0].strip() if img_match else ""
        aria = re.search(r'aria-label=["\'][^"\']*jersey number\s+([^"\']+?)\s+full bio["\']', card, flags=re.I)
        jersey = _clean(aria.group(1)) if aria else ""
        position = _field_from_card(card, "person-position-short")
        class_year = _field_from_card(card, "person-season")
        rows[key] = {
            "player_name": name,
            "player_id": _extract_profile_id(href),
            "profile_url": urljoin(base + "/", href),
            "headshot": headshot,
            "position": position,
            "jersey_number": jersey,
            "class_year": class_year,
            "roster_url": roster_url,
            "source": "Official team athletics roster",
        }
    return rows


def resolve_player_identity(
    player_name: Any,
    away_team: Any,
    home_team: Any,
    team_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Verify the player on exactly one current roster from the NCAA game."""
    index = team_index or load_ncaa_team_index()
    player_key = _norm(player_name)
    candidates: list[dict[str, Any]] = []
    for side, team_name in (("away", away_team), ("home", home_team)):
        team = lookup_team(team_name, index)
        if not team:
            continue
        roster = load_official_roster(str(team.get("ncaa_school_slug") or ""))
        row = roster.get(player_key)
        if not row:
            aliases = [candidate for candidate in roster.values() if _player_alias_match(_clean(player_name), _clean(candidate.get("player_name")))]
            row = aliases[0] if len(aliases) == 1 else None
        if not row:
            continue
        candidates.append({
            **row,
            "team_side": side,
            "team": _clean(team_name),
            "team_id": team.get("ncaa_team_id"),
            "team_logo": team.get("logo"),
            "team_record": team.get("record"),
            "ncaa_school_slug": team.get("ncaa_school_slug"),
        })
    return candidates[0] if len(candidates) == 1 else None


def enrich_top_picks_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    index = load_ncaa_team_index()
    out = dict(payload)
    game_rows: list[dict[str, Any]] = []
    prop_rows: list[dict[str, Any]] = []
    team_hits = player_hits = 0

    def enrich_teams(raw: Mapping[str, Any]) -> dict[str, Any]:
        nonlocal team_hits
        row = dict(raw)
        for side in ("away", "home"):
            team_name = row.get(f"{side}_team")
            team = lookup_team(team_name, index)
            if team:
                row[f"{side}_record"] = team.get("record") or "NOT_AVAILABLE"
                row[f"{side}_logo"] = team.get("logo") or None
                row[f"{side}_team_id"] = team.get("ncaa_team_id") or None
                row[f"{side}_record_source"] = "NCAA"
                row[f"{side}_logo_source"] = "NCAA"
                team_hits += 1
            else:
                row[f"{side}_record"] = "NOT_AVAILABLE"
                row[f"{side}_record_source"] = "NOT_AVAILABLE"
                row[f"{side}_logo_source"] = "NOT_AVAILABLE"
        return row

    for raw in payload.get("game_picks") or []:
        if isinstance(raw, Mapping):
            game_rows.append(enrich_teams(raw))

    for raw in payload.get("player_props") or []:
        if not isinstance(raw, Mapping):
            continue
        row = enrich_teams(raw)
        identity = resolve_player_identity(row.get("player_name"), row.get("away_team"), row.get("home_team"), index)
        if identity:
            player_hits += 1
            row.update({
                "player_id": identity.get("player_id") or None,
                "player_team": identity.get("team") or None,
                "player_team_id": identity.get("team_id") or None,
                "player_team_logo": identity.get("team_logo") or None,
                "player_headshot": identity.get("headshot") or None,
                "position": identity.get("position") or None,
                "jersey_number": identity.get("jersey_number") or None,
                "class_year": identity.get("class_year") or None,
                "player_profile_url": identity.get("profile_url") or None,
                "player_identity_status": "VERIFIED",
                "player_identity_source": "Official team athletics roster",
            })
            row["opponent"] = row.get("home_team") if identity.get("team_side") == "away" else row.get("away_team")
        else:
            row.update({
                "player_id": None,
                "player_team": None,
                "player_team_id": None,
                "player_team_logo": None,
                "player_headshot": None,
                "position": None,
                "jersey_number": None,
                "class_year": None,
                "player_profile_url": None,
                "player_identity_status": "NOT_AVAILABLE",
                "player_identity_source": "Official roster fallback exhausted",
                "opponent": None,
            })
        prop_rows.append(row)

    out["game_picks"] = game_rows
    out["player_props"] = prop_rows
    return out, {
        "team_identity_matches": team_hits,
        "player_identity_matches": player_hits,
        "game_rows": len(game_rows),
        "prop_rows": len(prop_rows),
    }


__all__ = [
    "NCAA_WIN_PCT_URL",
    "enrich_top_picks_payload",
    "load_ncaa_team_index",
    "load_official_roster",
    "lookup_team",
    "official_athletics_base",
    "resolve_player_identity",
]
