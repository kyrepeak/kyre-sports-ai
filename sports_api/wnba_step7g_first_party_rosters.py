"""Step 7G first-party current-roster adapter for frozen Step 4I availability.

The frozen Step 4B/4I path normally obtains league-wide current roster identity
from ``stats.wnba.com/commonallplayers``. Hosted runners have repeatedly timed
out on that transport. This isolated adapter instead reads each franchise's
official ``*.wnba.com/roster`` page. Those pages expose active roster cards as
links to canonical ``www.wnba.com/player/{player_id}`` pages, allowing current
membership and player identity to be verified without inventing IDs or relying
on a third party.

Official roster cards can contain more than one link to the same player (for
example a headshot link and a separate text link). The parser therefore groups
all roster-section links by official player ID and chooses the strongest
parseable identity candidate rather than treating a presentation-only duplicate
link as malformed data.

This module performs GET requests only. It does not write production state,
start schedulers, access sportsbooks, persist data, or change frozen providers.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from threading import Lock
from time import monotonic, sleep
from typing import Any
from urllib.parse import urlparse

import httpx

from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_rosters import WNBAStatsUpstreamError

SOURCE = "Official WNBA Team Roster Pages"
SOURCE_VARIANT = "wnba_team_roster_pages_player_links"
CACHE_TTL_SECONDS = 120
CACHE_MAX_ENTRIES = 8
MAX_PAGE_BYTES = 5_000_000
REQUEST_TIMEOUT_SECONDS = 12.0
REQUEST_ATTEMPTS = 2
MAX_WORKERS = 8

TEAM_ROSTER_HOSTS = {
    "atlanta-dream": "dream.wnba.com",
    "chicago-sky": "sky.wnba.com",
    "connecticut-sun": "sun.wnba.com",
    "dallas-wings": "wings.wnba.com",
    "golden-state-valkyries": "valkyries.wnba.com",
    "indiana-fever": "fever.wnba.com",
    "las-vegas-aces": "aces.wnba.com",
    "los-angeles-sparks": "sparks.wnba.com",
    "minnesota-lynx": "lynx.wnba.com",
    "new-york-liberty": "liberty.wnba.com",
    "phoenix-mercury": "mercury.wnba.com",
    "portland-fire": "fire.wnba.com",
    "seattle-storm": "storm.wnba.com",
    "toronto-tempo": "tempo.wnba.com",
    "washington-mystics": "mystics.wnba.com",
}

HTTP_HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
}

_PLAYER_PATH_RE = re.compile(r"^/player/(\d+)(?:/)?$")
_JERSEY_RE = re.compile(r"^#([^\s]+)\s+(.+)$")
_POSITION_VALUES = (
    "Guard-Forward",
    "Forward-Guard",
    "Forward-Center",
    "Center-Forward",
    "Guard-Center",
    "Center-Guard",
    "Guard",
    "Forward",
    "Center",
)

_CACHE: dict[int, dict[str, Any]] = {}
_CACHE_LOCK = Lock()


class _RosterHTMLParser(HTMLParser):
    """Collect visible text and player links only inside the roster section."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visible_parts: list[str] = []
        self.player_links: list[tuple[str, str]] = []
        self._in_roster = False
        self._href: str | None = None
        self._anchor_parts: list[str] = []
        self._anchor_in_roster = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        values = {str(key).casefold(): value for key, value in attrs}
        if lowered == "a":
            self._href = values.get("href")
            self._anchor_parts = []
            self._anchor_in_roster = self._in_roster
            return
        if lowered == "img" and self._href is not None and self._anchor_in_roster:
            alt = " ".join(str(values.get("alt") or "").split())
            if alt:
                self._anchor_parts.append(alt)

    def handle_data(self, data: str) -> None:
        text = " ".join(str(data).split())
        if not text:
            return
        self.visible_parts.append(text)

        folded = text.casefold()
        if "2026 team roster" in folded or folded == "team roster":
            self._in_roster = True
        elif "coaching staff" in folded:
            self._in_roster = False

        if self._href is not None and self._anchor_in_roster:
            self._anchor_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        if self._anchor_in_roster:
            text = " ".join(self._anchor_parts).strip()
            self.player_links.append((self._href, text))
        self._href = None
        self._anchor_parts = []
        self._anchor_in_roster = False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _player_id_from_href(href: str) -> int | None:
    raw = str(href or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or parsed.netloc.casefold() not in {"www.wnba.com", "wnba.com"}:
            return None
        path = parsed.path
    else:
        path = parsed.path or raw
    match = _PLAYER_PATH_RE.match(path)
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def _parse_card_text(text: str) -> tuple[str | None, str | None, str | None]:
    clean = " ".join(str(text or "").split())
    match = _JERSEY_RE.match(clean)
    if not match:
        return None, None, None
    jersey, body = match.groups()
    body = re.split(r"\s+PPG\b", body, maxsplit=1, flags=re.I)[0].strip()
    for position in _POSITION_VALUES:
        suffix = f" {position}"
        if body.casefold().endswith(suffix.casefold()):
            name = body[: -len(suffix)].strip()
            return jersey.strip() or None, name or None, position
    return jersey.strip() or None, body or None, None


def _plain_name_candidate(text: str) -> str | None:
    """Accept a name-only roster anchor/alt while rejecting labels and metrics."""
    clean = " ".join(str(text or "").split()).strip()
    if not clean or clean.startswith("#"):
        return None
    clean = re.split(r"\s+(?:PPG|RPG|APG)\b", clean, maxsplit=1, flags=re.I)[0].strip()
    folded = clean.casefold()
    if folded in {"view profile", "player profile", "read more", "roster"}:
        return None
    if any(character.isdigit() for character in clean):
        return None
    words = clean.split()
    if not 2 <= len(words) <= 6:
        return None
    allowed_punctuation = {" ", "-", "'", "’", "."}
    if not all(character.isalpha() or character in allowed_punctuation for character in clean):
        return None
    return clean


def _best_identity_candidate(texts: list[str]) -> tuple[str | None, str | None, str | None]:
    candidates: list[tuple[int, str | None, str, str | None]] = []
    for text in texts:
        jersey, name, position = _parse_card_text(text)
        if name:
            score = 100 + (10 if position else 0) + (5 if jersey else 0)
            candidates.append((score, jersey, name, position))
            continue
        plain = _plain_name_candidate(text)
        if plain:
            candidates.append((10, None, plain, None))
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda row: (row[0], len(row[2])), reverse=True)
    _, jersey, name, position = candidates[0]
    return jersey, name, position


def _parse_roster_html(html: str, *, team: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    parser = _RosterHTMLParser()
    try:
        parser.feed(str(html))
    except Exception as exc:
        raise WNBAStatsUpstreamError(
            f"Official WNBA roster HTML could not be parsed for {team['full_name']}."
        ) from exc

    visible = " ".join(parser.visible_parts)
    if "2026 Team Roster" not in visible and "Team Roster" not in visible:
        raise WNBAStatsUpstreamError(
            f"Official WNBA roster marker was not found for {team['full_name']}."
        )
    if "Coaching Staff" not in visible:
        raise WNBAStatsUpstreamError(
            f"Official WNBA coaching-staff boundary was not found for {team['full_name']}."
        )

    link_texts_by_player_id: dict[int, list[str]] = {}
    for href, anchor_text in parser.player_links:
        player_id = _player_id_from_href(href)
        if player_id is None:
            continue
        link_texts_by_player_id.setdefault(player_id, []).append(anchor_text)

    players: list[dict[str, Any]] = []
    unresolved_ids: list[int] = []
    for player_id, texts in sorted(link_texts_by_player_id.items()):
        jersey, name, position = _best_identity_candidate(texts)
        if not name:
            unresolved_ids.append(player_id)
            continue
        players.append(
            {
                "player_id": player_id,
                "full_name": name,
                "display_last_comma_first": None,
                "player_code": None,
                "player_slug": None,
                "from_year": None,
                "to_year": None,
                "roster_status": 1,
                "is_current_roster": True,
                "games_played_flag": None,
                "official_team_id": team.get("official_team_id"),
                "team_key": team["team_key"],
                "team_city": team.get("city"),
                "team_name": team.get("nickname"),
                "team_abbreviation": team.get("abbreviation"),
                "team_code": None,
                "team_slug": team.get("slug"),
                "jersey_number": jersey,
                "position": position,
                "headshot_url": f"https://cdn.wnba.com/headshots/wnba/latest/1040x760/{player_id}.png",
                "current_membership_source_url": source_url,
            }
        )

    if not 7 <= len(players) <= 20:
        raise WNBAStatsUpstreamError(
            f"Official WNBA roster page returned an implausible active-player count "
            f"({len(players)}) for {team['full_name']} "
            f"with {len(unresolved_ids)} unresolved roster-section player IDs."
        )
    if len(link_texts_by_player_id) > 20:
        raise WNBAStatsUpstreamError(
            f"Official WNBA roster section exposed an implausible number of unique "
            f"player IDs ({len(link_texts_by_player_id)}) for {team['full_name']}."
        )
    return players


def _fetch_team_roster(team: dict[str, Any]) -> dict[str, Any]:
    team_key = str(team["team_key"])
    host = TEAM_ROSTER_HOSTS.get(team_key)
    if not host:
        raise WNBAStatsUpstreamError(
            f"No certified official WNBA roster host is registered for {team['full_name']}."
        )
    url = f"https://{host}/roster"
    last_error: BaseException | None = None
    for attempt in range(1, REQUEST_ATTEMPTS + 1):
        try:
            response = httpx.get(
                url,
                headers=HTTP_HEADERS,
                timeout=REQUEST_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
            if not 0 < len(response.content) <= MAX_PAGE_BYTES:
                raise WNBAStatsUpstreamError(
                    f"Official WNBA roster page size was invalid for {team['full_name']}."
                )
            players = _parse_roster_html(response.text, team=team, source_url=url)
            return {
                "team_key": team_key,
                "source_url": url,
                "player_count": len(players),
                "players": players,
            }
        except WNBAStatsUpstreamError:
            raise
        except (httpx.HTTPError, OSError, TimeoutError) as exc:
            last_error = exc
            if attempt < REQUEST_ATTEMPTS:
                sleep(0.35 * attempt)
    raise WNBAStatsUpstreamError(
        f"Official WNBA roster page request failed for {team['full_name']} after "
        f"{REQUEST_ATTEMPTS} bounded attempts: {type(last_error).__name__ if last_error else 'unknown'}"
    ) from last_error


def get_first_party_current_players_dataset(
    season: int,
    *,
    current_roster_only: bool = True,
) -> dict[str, Any]:
    if current_roster_only is not True:
        raise ValueError(
            "Step 7G first-party roster adapter supports current_roster_only=True only."
        )
    teams = [dict(team) for team in get_wnba_teams(season)]
    if season != 2026:
        raise ValueError("Step 7G first-party roster adapter is certified for 2026 only.")

    now = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(season)
        if cached and cached["expires_at"] > now:
            result = deepcopy(cached["dataset"])
            result["cache_hit"] = True
            return result
        if cached:
            _CACHE.pop(season, None)

    expected_keys = {team["team_key"] for team in teams}
    configured_keys = set(TEAM_ROSTER_HOSTS)
    missing_hosts = sorted(expected_keys - configured_keys)
    extra_hosts = sorted(configured_keys - expected_keys)
    if missing_hosts or extra_hosts:
        raise WNBAStatsUpstreamError(
            "Step 7G roster host registry does not exactly match the 2026 team registry: "
            f"missing={missing_hosts}, extra={extra_hosts}."
        )

    rows: list[dict[str, Any]] = []
    source_urls: dict[str, str] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(teams))) as executor:
        futures = {executor.submit(_fetch_team_roster, team): team for team in teams}
        for future in as_completed(futures):
            team = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                failures.append(f"{team['team_key']}: {exc}")
                continue
            rows.extend(result["players"])
            source_urls[result["team_key"]] = result["source_url"]

    if failures:
        raise WNBAStatsUpstreamError(
            "One or more official WNBA roster pages could not be certified: "
            + "; ".join(sorted(failures))
        )

    player_ids = [row["player_id"] for row in rows]
    duplicates = sorted(value for value in set(player_ids) if player_ids.count(value) > 1)
    if duplicates:
        raise WNBAStatsUpstreamError(
            f"Official WNBA roster pages returned duplicate player IDs across teams: {duplicates}."
        )
    observed_team_keys = {row["team_key"] for row in rows}
    if observed_team_keys != expected_keys:
        raise WNBAStatsUpstreamError(
            "Official WNBA roster pages did not produce players for every registered team."
        )

    rows.sort(key=lambda row: (row["team_key"], row["full_name"], row["player_id"]))
    retrieved_at = _utc_now_iso()
    dataset = {
        "source": SOURCE,
        "source_url": "https://www.wnba.com/",
        "source_endpoint": "official team *.wnba.com/roster player links",
        "source_variant": SOURCE_VARIANT,
        "season": season,
        "current_roster_only": True,
        "retrieved_at_utc": retrieved_at,
        "cache_hit": False,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "player_count": len(rows),
        "players": rows,
        "team_source_urls": source_urls,
        "verification": {
            "all_registered_teams_loaded": True,
            "all_players_have_official_wnba_player_ids": True,
            "player_ids_unique_across_teams": True,
            "current_membership_from_official_team_roster_pages": True,
            "duplicate_presentation_links_collapsed_by_player_id": True,
            "third_party_sources_used": False,
            "production_provider_replaced": False,
        },
    }
    with _CACHE_LOCK:
        if len(_CACHE) >= CACHE_MAX_ENTRIES:
            _CACHE.pop(next(iter(_CACHE)), None)
        _CACHE[season] = {
            "dataset": deepcopy(dataset),
            "expires_at": now + CACHE_TTL_SECONDS,
        }
    return dataset
