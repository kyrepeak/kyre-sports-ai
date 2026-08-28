"""Step 7G first-party current-roster adapter for frozen Step 4I availability.

The frozen Step 4B/4I path normally obtains league-wide current roster identity
from ``stats.wnba.com/commonallplayers``. Hosted runners have repeatedly timed
out on that transport. This isolated adapter instead reads each franchise's
official ``*.wnba.com/roster`` page.

The live official page exposes two independent first-party identity surfaces in
its server response:
1. rendered TeamRoster player tiles containing headshot player IDs and names;
2. React Flight data containing playerId/playerName/playerNumber/position/teamId
   and the canonical ``www.wnba.com/player/{id}`` link.

Both surfaces must agree exactly for every active player. Any missing/duplicate
identity, mismatched team, or implausible roster size fails closed.

This module performs GET requests only. It does not write production state,
start schedulers, access sportsbooks, persist data, or modify frozen providers.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import re
from threading import Lock
from time import monotonic, sleep
from typing import Any
from urllib.parse import urlparse

import httpx

from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_rosters import WNBAStatsUpstreamError

SOURCE = "Official WNBA Team Roster Pages"
SOURCE_VARIANT = "wnba_team_roster_tiles_plus_react_flight_identity"
CACHE_TTL_SECONDS = 120
CACHE_MAX_ENTRIES = 8
MAX_PAGE_BYTES = 5_000_000
REQUEST_TIMEOUT_SECONDS = 12.0
REQUEST_ATTEMPTS = 2
MAX_WORKERS = 8
MIN_ROSTER_PLAYERS = 7
MAX_ROSTER_PLAYERS = 20

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
_HEADSHOT_ID_RE = re.compile(r"/headshots/wnba/(?:latest|\d+)/\d+x\d+/(\d+)\.png(?:[?#].*)?$", re.I)
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


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


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


def _headshot_player_id(src: str | None) -> int | None:
    if not src:
        return None
    parsed = urlparse(str(src).strip())
    if parsed.scheme and parsed.scheme != "https":
        return None
    if parsed.netloc and parsed.netloc.casefold() != "cdn.wnba.com":
        return None
    match = _HEADSHOT_ID_RE.search(parsed.path)
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def _parse_card_text(text: str) -> tuple[str | None, str | None, str | None]:
    """Compatibility helper retained for isolated regression tests."""
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
    """Compatibility helper for safe name-only identity candidates."""
    clean = " ".join(str(text or "").split()).strip()
    if not clean or clean.startswith("#"):
        return None
    folded = clean.casefold()
    if folded in {
        "view profile",
        "player profile",
        "read more",
        "roster",
        "show more",
    } or "headshot" in folded:
        return None
    if any(character.isdigit() for character in clean):
        return None
    words = clean.split()
    if not 2 <= len(words) <= 6:
        return None
    allowed = {" ", "-", "'", "’", "."}
    if not all(character.isalpha() or character in allowed for character in clean):
        return None
    return clean


class _RosterTileParser(HTMLParser):
    """Extract rendered official TeamRoster tiles from server HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visible_parts: list[str] = []
        self.tiles: list[dict[str, Any]] = []
        self.all_player_link_ids: list[int] = []
        self._tile: dict[str, Any] | None = None
        self._capture: str | None = None
        self._in_subtitle = False
        self._subtitle_span = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        values = {str(key).casefold(): value for key, value in attrs}
        class_name = str(values.get("class") or "")

        if lowered == "li" and "teamroster_playertile" in class_name.casefold():
            if self._tile is not None:
                self._tile["malformed_nested_tile"] = True
            self._tile = {
                "href_ids": [],
                "headshot_id": None,
                "headshot_alt": None,
                "name": None,
                "jersey_number": None,
                "position": None,
            }

        if lowered == "a":
            player_id = _player_id_from_href(str(values.get("href") or ""))
            if player_id is not None:
                self.all_player_link_ids.append(player_id)
                if self._tile is not None:
                    self._tile["href_ids"].append(player_id)

        if self._tile is None:
            return

        if lowered == "img":
            player_id = _headshot_player_id(values.get("src"))
            if player_id is not None:
                existing = self._tile.get("headshot_id")
                if existing is not None and existing != player_id:
                    self._tile["conflicting_headshot_ids"] = True
                self._tile["headshot_id"] = player_id
                self._tile["headshot_alt"] = _clean(values.get("alt"))
            return

        folded_class = class_name.casefold()
        if lowered == "h3" and "playertile__player__name" in folded_class:
            self._capture = "name"
        elif lowered == "span" and "playertile__number__digit" in folded_class:
            self._capture = "jersey_number"
        elif lowered == "p" and "playertile__player__subtitle" in folded_class:
            self._in_subtitle = True
        elif lowered == "span" and self._in_subtitle and self._tile.get("position") is None:
            self._subtitle_span = True
            self._capture = "position"

    def handle_data(self, data: str) -> None:
        text = _clean(data)
        if text is None:
            return
        self.visible_parts.append(text)
        if self._tile is not None and self._capture is not None:
            current = self._tile.get(self._capture)
            if not current:
                self._tile[self._capture] = text

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in {"h3", "span"}:
            if lowered == "span" and self._subtitle_span:
                self._subtitle_span = False
            self._capture = None
        if lowered == "p" and self._in_subtitle:
            self._in_subtitle = False
            self._subtitle_span = False
            self._capture = None
        if lowered == "li" and self._tile is not None:
            self.tiles.append(self._tile)
            self._tile = None
            self._capture = None
            self._in_subtitle = False
            self._subtitle_span = False


def _decode_flight_html(html: str) -> str:
    # React Flight strings escape JSON quotes with one or more backslashes. Remove
    # only the quote-escape slashes, leaving unicode/string escapes intact.
    return re.sub(r"\\+(?=\")", "", html)


def _json_unescape(value: str) -> str:
    try:
        return str(json.loads(f'"{value}"'))
    except Exception:
        return value


def _flight_roster_rows(html: str) -> list[dict[str, Any]]:
    normalized = _decode_flight_html(html)
    # Bound each search window so one malformed object cannot swallow unrelated
    # page data. The observed official object is well under 1,500 characters.
    pattern = re.compile(
        r'"playerId":(?P<player_id>\d+)'
        r'(?P<body>.{0,1600}?)'
        r'"playerLink":"https://www\.wnba\.com/player/(?P<link_id>\d+)"',
        re.S,
    )
    field_patterns = {
        "player_name": re.compile(r'"playerName":"([^"]+)"'),
        "player_number": re.compile(r'"playerNumber":"([^"]*)"'),
        "position": re.compile(r'"position":"([^"]*)"'),
        "team_id": re.compile(r'"teamId":"?(\d+)"?'),
    }
    by_id: dict[int, dict[str, Any]] = {}
    conflicts: set[int] = set()
    for match in pattern.finditer(normalized):
        player_id = int(match.group("player_id"))
        link_id = int(match.group("link_id"))
        if player_id != link_id:
            conflicts.add(player_id)
            continue
        body = match.group("body")
        row: dict[str, Any] = {
            "player_id": player_id,
            "player_link_id": link_id,
        }
        complete = True
        for key, field_pattern in field_patterns.items():
            field_match = field_pattern.search(body)
            if field_match is None:
                complete = False
                break
            raw_value = field_match.group(1)
            row[key] = _json_unescape(raw_value) if key != "team_id" else raw_value
        if not complete:
            continue
        existing = by_id.get(player_id)
        if existing is not None and existing != row:
            conflicts.add(player_id)
            continue
        by_id[player_id] = row
    if conflicts:
        raise WNBAStatsUpstreamError(
            f"Official WNBA React roster data returned conflicting rows for player IDs {sorted(conflicts)}."
        )
    return list(by_id.values())


def _parse_roster_html(
    html: str,
    *,
    team: dict[str, Any],
    source_url: str,
) -> list[dict[str, Any]]:
    parser = _RosterTileParser()
    try:
        parser.feed(str(html))
    except Exception as exc:
        raise WNBAStatsUpstreamError(
            f"Official WNBA roster HTML could not be parsed for {team['full_name']}."
        ) from exc

    visible = " ".join(parser.visible_parts)
    if "Team Roster" not in visible:
        raise WNBAStatsUpstreamError(
            f"Official WNBA roster marker was not found for {team['full_name']}."
        )
    if "Coaching Staff" not in visible:
        raise WNBAStatsUpstreamError(
            f"Official WNBA coaching-staff boundary was not found for {team['full_name']}."
        )

    tiles_by_id: dict[int, dict[str, Any]] = {}
    for tile in parser.tiles:
        if tile.get("malformed_nested_tile") or tile.get("conflicting_headshot_ids"):
            raise WNBAStatsUpstreamError(
                f"Official WNBA roster tile structure was ambiguous for {team['full_name']}."
            )
        player_id = tile.get("headshot_id")
        name = _clean(tile.get("name"))
        if not isinstance(player_id, int) or player_id <= 0 or name is None:
            raise WNBAStatsUpstreamError(
                f"Official WNBA roster tile was missing player ID/name for {team['full_name']}."
            )
        href_ids = {int(value) for value in tile.get("href_ids", [])}
        if href_ids and href_ids != {player_id}:
            raise WNBAStatsUpstreamError(
                f"Official WNBA roster tile link/headshot identity disagreed for {team['full_name']}."
            )
        alt = _clean(tile.get("headshot_alt"))
        if alt:
            expected_alt = f"{name} headshot".casefold()
            if alt.casefold() != expected_alt:
                raise WNBAStatsUpstreamError(
                    f"Official WNBA roster tile name/headshot alt disagreed for player {player_id}."
                )
        if player_id in tiles_by_id:
            raise WNBAStatsUpstreamError(
                f"Official WNBA roster HTML returned duplicate player tile {player_id}."
            )
        tiles_by_id[player_id] = tile

    if not MIN_ROSTER_PLAYERS <= len(tiles_by_id) <= MAX_ROSTER_PLAYERS:
        raise WNBAStatsUpstreamError(
            f"Official WNBA roster page returned an implausible player-tile count "
            f"({len(tiles_by_id)}) for {team['full_name']}."
        )

    flight_rows = _flight_roster_rows(str(html))
    flight_by_id = {int(row["player_id"]): row for row in flight_rows}
    if set(flight_by_id) != set(tiles_by_id):
        raise WNBAStatsUpstreamError(
            f"Official WNBA roster rendered/React identity surfaces disagree for {team['full_name']}: "
            f"tile_ids={len(tiles_by_id)}, flight_ids={len(flight_by_id)}."
        )

    page_link_ids = set(parser.all_player_link_ids)
    if not set(tiles_by_id).issubset(page_link_ids):
        raise WNBAStatsUpstreamError(
            f"Official WNBA roster tiles are missing canonical player links for {team['full_name']}."
        )

    expected_team_id = str(team.get("official_team_id") or "")
    players: list[dict[str, Any]] = []
    for player_id, tile in tiles_by_id.items():
        flight = flight_by_id[player_id]
        tile_name = _clean(tile.get("name"))
        flight_name = _clean(flight.get("player_name"))
        if tile_name is None or flight_name is None or tile_name.casefold() != flight_name.casefold():
            raise WNBAStatsUpstreamError(
                f"Official WNBA roster tile/React name mismatch for player {player_id}."
            )
        try:
            flight_team_id = int(flight.get("team_id"))
        except (TypeError, ValueError) as exc:
            raise WNBAStatsUpstreamError(
                f"Official WNBA roster React team ID was invalid for player {player_id}."
            ) from exc
        if flight_team_id <= 0:
            raise WNBAStatsUpstreamError(
                f"Official WNBA roster React team ID was invalid for player {player_id}."
            )
        if expected_team_id and str(flight_team_id) != expected_team_id:
            raise WNBAStatsUpstreamError(
                f"Official WNBA roster React team ID mismatch for player {player_id}."
            )

        tile_number = _clean(tile.get("jersey_number"))
        flight_number = _clean(flight.get("player_number"))
        if tile_number and flight_number and tile_number != flight_number:
            raise WNBAStatsUpstreamError(
                f"Official WNBA roster jersey mismatch for player {player_id}."
            )
        tile_position = _clean(tile.get("position"))
        flight_position = _clean(flight.get("position"))
        if tile_position and flight_position and tile_position.casefold() != flight_position.casefold():
            raise WNBAStatsUpstreamError(
                f"Official WNBA roster position mismatch for player {player_id}."
            )

        players.append(
            {
                "player_id": player_id,
                "full_name": flight_name,
                "display_last_comma_first": None,
                "player_code": None,
                "player_slug": None,
                "from_year": None,
                "to_year": None,
                "roster_status": 1,
                "is_current_roster": True,
                "games_played_flag": None,
                "official_team_id": flight_team_id,
                "team_key": team["team_key"],
                "team_city": team.get("city"),
                "team_name": team.get("nickname"),
                "team_abbreviation": team.get("abbreviation"),
                "team_code": None,
                "team_slug": team.get("slug"),
                "jersey_number": flight_number or tile_number,
                "position": flight_position or tile_position,
                "headshot_url": f"https://cdn.wnba.com/headshots/wnba/latest/1040x760/{player_id}.png",
                "current_membership_source_url": source_url,
            }
        )

    players.sort(key=lambda row: (row["full_name"], row["player_id"]))
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
        "source_endpoint": "official team roster rendered tiles + React Flight identity",
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
            "rendered_tiles_match_react_flight_identity": True,
            "canonical_player_links_verified": True,
            "react_team_ids_match_registry": True,
            "current_membership_from_official_team_roster_pages": True,
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
