"""Read-only FanDuel MLB player-prop collector with exact MLBAM identity.

The collector publishes only markets that satisfy the frozen Step 8A contract:
one exact official MLB game/player identity, one positive line, and explicit
FanDuel Over and Under prices. FanDuel threshold ladders (for example 1+ hits)
are observed but never converted into synthetic two-way prices.

Player names are display metadata only. Identity reconciliation never compares,
normalizes, searches, or falls back to a player name.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sports_api.collectors.mlb_fanduel_direct import (
    FANDUEL_BASE_URL,
    FANDUEL_HEADERS,
    FANDUEL_PUBLIC_WEB_KEY,
    FANDUEL_REGION,
    fetch_fanduel_mlb_landing,
    fetch_mlb_schedule,
    parse_fanduel_matchup,
    reconcile_official_game,
)

SNAPSHOT_DATA_TYPE = "mlb_live_player_prop_snapshot_v1"
SCHEMA_VERSION = 1
SOURCE = "FanDuel"
TRANSPORT = "anonymous_public_get_only"
HTTP_METHODS = ["GET"]

PITCHER_STRIKEOUTS = "pitcher_strikeouts"
PLAYER_HITS = "player_hits"
HITS_RUNS_RBI = "hits_runs_rbi"
SUPPORTED_MARKET_TYPES = frozenset({PITCHER_STRIKEOUTS, PLAYER_HITS, HITS_RUNS_RBI})

FANDUEL_FDX_BASE_URL = "https://fdx-api.sportsbook.fanduel.com/api"
MLB_STATSAPI_BASE_URL = "https://statsapi.mlb.com/api/v1"
MAX_RESPONSE_BYTES = 20_000_000
DEFAULT_TIMEOUT_SECONDS = 25
EASTERN = ZoneInfo("America/New_York")
PROP_TABS = ("pitcher-props", "batter-props", "player-combos")
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


class MLBPlayerPropCollectorError(RuntimeError):
    """Raised when a player-prop payload cannot be safely normalized."""


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        rows: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("_attachment_key", str(key))
                rows.append(row)
        return rows
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _get_json(
    url: str,
    params: Mapping[str, Any] | None = None,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    query = urlencode({str(k): str(v) for k, v in (params or {}).items()})
    target = f"{url}?{query}" if query else url
    request = Request(target, headers=dict(headers or {}), method="GET")
    with urlopen(request, timeout=timeout) as response:
        status = int(getattr(response, "status", 0) or 0)
        if status != 200:
            raise MLBPlayerPropCollectorError(f"GET {url} returned HTTP {status}")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise MLBPlayerPropCollectorError(f"GET {url} exceeded {MAX_RESPONSE_BYTES} bytes")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MLBPlayerPropCollectorError(f"GET {url} did not return valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise MLBPlayerPropCollectorError(f"GET {url} did not return a JSON object")
    return payload


def fetch_fanduel_event_prop_tab(
    event_id: str | int,
    tab: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if tab not in PROP_TABS:
        raise ValueError(f"unsupported FanDuel player-prop tab: {tab!r}")
    return _get_json(
        f"{FANDUEL_BASE_URL}/sbapi/event-page",
        {"_ak": FANDUEL_PUBLIC_WEB_KEY, "eventId": str(event_id), "tab": tab},
        headers=FANDUEL_HEADERS,
        timeout=timeout,
    )


def fetch_fanduel_event_players(
    event_id: str | int,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return _get_json(
        f"{FANDUEL_FDX_BASE_URL}/v1/live/event/{event_id}/players",
        headers=FANDUEL_HEADERS,
        timeout=timeout,
    )


def fetch_mlb_active_roster(
    team_id: int,
    slate_date: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return _get_json(
        f"{MLB_STATSAPI_BASE_URL}/teams/{int(team_id)}/roster",
        {"rosterType": "active", "date": slate_date},
        headers={"Accept": "application/json", "User-Agent": FANDUEL_HEADERS["User-Agent"]},
        timeout=timeout,
    )


def _iso_utc(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        raise MLBPlayerPropCollectorError("missing ISO timestamp")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise MLBPlayerPropCollectorError(f"invalid ISO timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise MLBPlayerPropCollectorError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _event_id(event: Mapping[str, Any]) -> str:
    return str(
        event.get("eventId")
        or event.get("id")
        or event.get("_attachment_key")
        or ""
    ).strip()


def _event_name(event: Mapping[str, Any]) -> str:
    return str(event.get("name") or event.get("eventName") or event.get("displayName") or "").strip()


def _official_team_id(game: Mapping[str, Any], side: str) -> int:
    teams = game.get("teams") or {}
    side_row = teams.get(side) or {} if isinstance(teams, Mapping) else {}
    team = side_row.get("team") or {} if isinstance(side_row, Mapping) else {}
    try:
        team_id = int(team.get("id"))
    except (TypeError, ValueError) as exc:
        raise MLBPlayerPropCollectorError(f"official MLB game is missing {side} team id") from exc
    if team_id <= 0:
        raise MLBPlayerPropCollectorError(f"official MLB game has invalid {side} team id")
    return team_id


def _headshot_uuid(value: Any) -> str | None:
    matches = UUID_RE.findall(str(value or ""))
    return matches[0].casefold() if len(matches) == 1 else None


def _position_bucket(value: Any) -> str:
    position = str(value or "").strip().upper()
    if position in {"SP", "RP", "P"}:
        return "P"
    if position in {"LF", "CF", "RF", "OF"}:
        return "OF"
    return position


def reconcile_fanduel_player_to_mlbam(
    fdx_player: Mapping[str, Any],
    *,
    official_team_by_fanduel_abbr: Mapping[str, int],
    official_rosters_by_team: Mapping[int, list[dict[str, Any]]],
) -> int | None:
    """Resolve one FDX player by side/team + jersey + compatible position only.

    No player-name field is read. Zero or multiple official matches fail closed.
    """
    team_abbr = str(fdx_player.get("team") or "").strip().upper()
    team_id = official_team_by_fanduel_abbr.get(team_abbr)
    jersey_number = str(fdx_player.get("number") or "").strip()
    provider_position = _position_bucket(fdx_player.get("position"))
    if team_id is None or not jersey_number or not provider_position:
        return None

    matches: list[int] = []
    for roster_row in official_rosters_by_team.get(int(team_id), []):
        if str(roster_row.get("jerseyNumber") or "").strip() != jersey_number:
            continue
        official_position = _position_bucket((roster_row.get("position") or {}).get("abbreviation"))
        if not official_position or official_position != provider_position:
            continue
        person = roster_row.get("person") or {}
        try:
            person_id = int(person.get("id"))
        except (TypeError, ValueError):
            continue
        if person_id > 0:
            matches.append(person_id)
    unique_matches = sorted(set(matches))
    return unique_matches[0] if len(unique_matches) == 1 else None


def _provider_market_type(market: Mapping[str, Any]) -> str:
    return str(
        market.get("marketType")
        or market.get("marketTypeCode")
        or market.get("type")
        or ""
    ).strip().upper()


def market_family(provider_market_type: Any) -> str | None:
    """Map known FanDuel player market families without reading player names."""
    market = str(provider_market_type or "").strip().upper()
    if market.startswith("PITCHER_") and "STRIKEOUT" in market:
        return PITCHER_STRIKEOUTS
    if "HITS" in market and "RUN" in market and "RBI" in market:
        return HITS_RUNS_RBI
    if (
        market == "PLAYER_TO_RECORD_A_HIT"
        or re.fullmatch(r"PLAYER_TO_RECORD_\d+\+_HITS", market) is not None
        or "TOTAL_HITS" in market
    ):
        return PLAYER_HITS
    return None


def _market_is_open_pregame(market: Mapping[str, Any]) -> bool:
    status = str(market.get("marketStatus") or market.get("status") or "").strip().upper()
    return status == "OPEN" and market.get("inPlay") is not True


def _active_player_runners(market: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        runner
        for runner in _rows(market.get("runners"))
        if runner.get("isPlayerSelection") is True
        and str(runner.get("runnerStatus") or "").strip().upper() in {"", "ACTIVE"}
    ]


def _runner_role(runner: Mapping[str, Any]) -> str:
    result = runner.get("result") or {}
    return str(result.get("type") or "").strip().upper() if isinstance(result, Mapping) else ""


def _positive_line(value: Any) -> float:
    if isinstance(value, bool):
        raise MLBPlayerPropCollectorError("boolean line is invalid")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise MLBPlayerPropCollectorError("player-prop line is not numeric") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise MLBPlayerPropCollectorError("player-prop line must be finite and positive")
    return parsed


def _american_odds(runner: Mapping[str, Any]) -> int:
    win = runner.get("winRunnerOdds") or {}
    display = win.get("americanDisplayOdds") or {} if isinstance(win, Mapping) else {}
    value = display.get("americanOddsInt") if isinstance(display, Mapping) else None
    if value is None and isinstance(display, Mapping):
        value = display.get("americanOdds")
    if isinstance(value, bool):
        raise MLBPlayerPropCollectorError("boolean American odds are invalid")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise MLBPlayerPropCollectorError("player-prop runner has no valid American odds") from exc
    if not math.isfinite(parsed) or parsed == 0 or not parsed.is_integer():
        raise MLBPlayerPropCollectorError("player-prop American odds must be a nonzero integer")
    return int(parsed)


def _selection_id(runner: Mapping[str, Any]) -> str:
    value = runner.get("selectionId")
    if isinstance(value, bool) or value is None:
        return ""
    return str(value).strip()


def _player_maps(
    fdx_players: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    raw_map = fdx_players.get("playerMap")
    if not isinstance(raw_map, Mapping):
        raise MLBPlayerPropCollectorError("FanDuel FDX playerMap is missing")

    players: dict[str, dict[str, Any]] = {}
    selection_to_players: dict[str, list[str]] = {}
    for provider_key, raw_player in raw_map.items():
        if not isinstance(raw_player, Mapping):
            continue
        key = str(provider_key).strip()
        if not key:
            continue
        player = dict(raw_player)
        players[key] = player
        for raw_selection in player.get("selectionIds") or []:
            if isinstance(raw_selection, bool) or raw_selection is None:
                continue
            selection = str(raw_selection).strip()
            if selection:
                selection_to_players.setdefault(selection, []).append(key)
    return players, selection_to_players


def _provider_player_for_two_way_market(
    over: Mapping[str, Any],
    under: Mapping[str, Any],
    *,
    players: Mapping[str, dict[str, Any]],
    selection_to_players: Mapping[str, list[str]],
) -> tuple[str, dict[str, Any]]:
    keys: list[str] = []
    runner_headshots: list[str] = []
    for runner in (over, under):
        selection = _selection_id(runner)
        matches = selection_to_players.get(selection) or []
        if len(matches) != 1:
            raise MLBPlayerPropCollectorError("runner selection does not map to one FDX player")
        keys.append(matches[0])
        headshot = _headshot_uuid(runner.get("logo"))
        if headshot is None:
            raise MLBPlayerPropCollectorError("runner has no unique FanDuel headshot identity")
        runner_headshots.append(headshot)

    if keys[0] != keys[1]:
        raise MLBPlayerPropCollectorError("Over and Under runners map to different FDX players")
    if runner_headshots[0] != runner_headshots[1]:
        raise MLBPlayerPropCollectorError("Over and Under runners have different headshot identities")

    provider_key = keys[0]
    player = players.get(provider_key)
    if not isinstance(player, Mapping):
        raise MLBPlayerPropCollectorError("FDX player identity is missing")
    player_headshot = _headshot_uuid(player.get("image"))
    if player_headshot is None or player_headshot != runner_headshots[0]:
        raise MLBPlayerPropCollectorError("prop headshot identity does not match FDX player")
    return provider_key, dict(player)


def normalize_two_way_player_market(
    market: Mapping[str, Any],
    *,
    official_game_id: int,
    source_event_id: str,
    players: Mapping[str, dict[str, Any]],
    selection_to_players: Mapping[str, list[str]],
    official_team_by_fanduel_abbr: Mapping[str, int],
    official_rosters_by_team: Mapping[int, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    """Normalize one true FanDuel Over/Under player market or fail closed."""
    if not _market_is_open_pregame(market):
        return None
    family = market_family(_provider_market_type(market))
    if family is None:
        return None

    runners = _active_player_runners(market)
    if len(runners) != 2:
        return None
    role_map = {_runner_role(runner): runner for runner in runners}
    if set(role_map) != {"OVER", "UNDER"}:
        return None
    over = role_map["OVER"]
    under = role_map["UNDER"]

    over_line = _positive_line(over.get("handicap"))
    under_line = _positive_line(under.get("handicap"))
    if over_line != under_line:
        raise MLBPlayerPropCollectorError("Over and Under runners have mismatched lines")

    _, fdx_player = _provider_player_for_two_way_market(
        over,
        under,
        players=players,
        selection_to_players=selection_to_players,
    )
    official_player_id = reconcile_fanduel_player_to_mlbam(
        fdx_player,
        official_team_by_fanduel_abbr=official_team_by_fanduel_abbr,
        official_rosters_by_team=official_rosters_by_team,
    )
    if official_player_id is None:
        raise MLBPlayerPropCollectorError("FDX player has no unique name-free MLBAM roster match")

    source_market_id = str(market.get("marketId") or market.get("_attachment_key") or "").strip()
    if not source_market_id:
        raise MLBPlayerPropCollectorError("FanDuel player market has no source market id")

    return {
        "official_game_id": int(official_game_id),
        "official_player_id": int(official_player_id),
        "player_name": str(fdx_player.get("name") or "").strip() or None,
        "market_type": family,
        "line": over_line,
        "over_odds": _american_odds(over),
        "under_odds": _american_odds(under),
        "sportsbook": SOURCE,
        "source_event_id": source_event_id,
        "source_market_id": source_market_id,
    }


def _official_roster_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in payload.get("roster") or [] if isinstance(row, Mapping)]


def _normalize_event(
    *,
    event: Mapping[str, Any],
    schedule_payload: Mapping[str, Any],
    tab_fetcher: Callable[[str, str], Mapping[str, Any]],
    players_fetcher: Callable[[str], Mapping[str, Any]],
    roster_fetcher: Callable[[int, str], Mapping[str, Any]],
    slate_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    source_event_id = _event_id(event)
    event_name = _event_name(event)
    away_name, home_name = parse_fanduel_matchup(event_name)
    official_game, _ = reconcile_official_game(
        schedule_payload,
        away_team=away_name,
        home_team=home_name,
        sportsbook_start_utc=str(event.get("openDate") or ""),
    )
    try:
        official_game_id = int(official_game.get("gamePk"))
    except (TypeError, ValueError) as exc:
        raise MLBPlayerPropCollectorError("official MLB game is missing gamePk") from exc
    if official_game_id <= 0:
        raise MLBPlayerPropCollectorError("official MLB game has invalid gamePk")

    away_team_id = _official_team_id(official_game, "away")
    home_team_id = _official_team_id(official_game, "home")
    fdx_payload = dict(players_fetcher(source_event_id))
    fdx_event = fdx_payload.get("event") or {}
    if not isinstance(fdx_event, Mapping):
        raise MLBPlayerPropCollectorError("FanDuel FDX event metadata is missing")
    away_abbr = str((fdx_event.get("awayTeam") or {}).get("abbrName") or "").strip().upper()
    home_abbr = str((fdx_event.get("homeTeam") or {}).get("abbrName") or "").strip().upper()
    if not away_abbr or not home_abbr or away_abbr == home_abbr:
        raise MLBPlayerPropCollectorError("FanDuel FDX team-side abbreviations are invalid")
    official_team_by_fanduel_abbr = {away_abbr: away_team_id, home_abbr: home_team_id}

    official_rosters_by_team = {
        away_team_id: _official_roster_rows(roster_fetcher(away_team_id, slate_date)),
        home_team_id: _official_roster_rows(roster_fetcher(home_team_id, slate_date)),
    }
    players, selection_to_players = _player_maps(fdx_payload)

    candidates: list[dict[str, Any]] = []
    rejected_props: list[dict[str, Any]] = []
    contract_unavailable = {PLAYER_HITS: 0, HITS_RUNS_RBI: 0, PITCHER_STRIKEOUTS: 0}

    for tab in PROP_TABS:
        tab_payload = dict(tab_fetcher(source_event_id, tab))
        attachments = tab_payload.get("attachments") or {}
        markets = _rows(attachments.get("markets")) if isinstance(attachments, Mapping) else []
        for market in markets:
            family = market_family(_provider_market_type(market))
            if family is None or not _market_is_open_pregame(market):
                continue
            runners = _active_player_runners(market)
            role_set = {_runner_role(runner) for runner in runners}
            is_contract_two_way = len(runners) == 2 and role_set == {"OVER", "UNDER"}
            if not is_contract_two_way:
                contract_unavailable[family] += 1
                continue
            try:
                normalized = normalize_two_way_player_market(
                    market,
                    official_game_id=official_game_id,
                    source_event_id=source_event_id,
                    players=players,
                    selection_to_players=selection_to_players,
                    official_team_by_fanduel_abbr=official_team_by_fanduel_abbr,
                    official_rosters_by_team=official_rosters_by_team,
                )
            except Exception as exc:
                rejected_props.append(
                    {
                        "official_game_id": official_game_id,
                        "source_event_id": source_event_id,
                        "source_market_id": str(market.get("marketId") or market.get("_attachment_key") or "") or None,
                        "provider_market_type": _provider_market_type(market) or None,
                        "market_type": family,
                        "reason": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            if normalized is not None:
                candidates.append(normalized)

    # Step 8A treats duplicate exact identities as globally fatal. Resolve safely
    # here: identical repeated attachments collapse; multiple distinct markets for
    # the same exact identity are all omitted rather than leaking a duplicate.
    grouped: dict[tuple[int, int, str], dict[str, dict[str, Any]]] = {}
    for prop in candidates:
        identity = (
            int(prop["official_game_id"]),
            int(prop["official_player_id"]),
            str(prop["market_type"]),
        )
        grouped.setdefault(identity, {})[str(prop["source_market_id"])] = prop

    props: list[dict[str, Any]] = []
    for identity, by_market_id in grouped.items():
        if len(by_market_id) == 1:
            props.append(next(iter(by_market_id.values())))
            continue
        rejected_props.append(
            {
                "official_game_id": identity[0],
                "official_player_id": identity[1],
                "market_type": identity[2],
                "reason": "ambiguous_multiple_contract_markets_for_exact_identity",
                "source_market_ids": sorted(by_market_id),
            }
        )

    props.sort(key=lambda row: (row["official_game_id"], row["official_player_id"], row["market_type"]))
    return props, rejected_props, contract_unavailable


def collect_live_mlb_player_props(
    *,
    now_utc: datetime | None = None,
    max_events: int = 30,
    landing_fetcher: Callable[[], Mapping[str, Any]] | None = None,
    tab_fetcher: Callable[[str, str], Mapping[str, Any]] | None = None,
    players_fetcher: Callable[[str], Mapping[str, Any]] | None = None,
    schedule_fetcher: Callable[[str], Mapping[str, Any]] | None = None,
    roster_fetcher: Callable[[int, str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Collect contract-compliant FanDuel MLB player props using GET requests only."""
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if max_events <= 0:
        raise ValueError("max_events must be positive")

    get_landing = landing_fetcher or fetch_fanduel_mlb_landing
    get_tab = tab_fetcher or (lambda event_id, tab: fetch_fanduel_event_prop_tab(event_id, tab))
    get_players = players_fetcher or (lambda event_id: fetch_fanduel_event_players(event_id))
    get_schedule = schedule_fetcher or fetch_mlb_schedule
    get_roster = roster_fetcher or (lambda team_id, slate_date: fetch_mlb_active_roster(team_id, slate_date))

    landing = dict(get_landing())
    attachments = landing.get("attachments") or {}
    if not isinstance(attachments, Mapping):
        raise MLBPlayerPropCollectorError("FanDuel MLB landing page has no attachments object")
    landing_events = _rows(attachments.get("events"))

    candidates: list[dict[str, Any]] = []
    for event in landing_events:
        if " @ " not in _event_name(event):
            continue
        start_text = str(event.get("openDate") or "").strip()
        if not start_text:
            continue
        try:
            start_utc = _iso_utc(start_text)
        except MLBPlayerPropCollectorError:
            continue
        if start_utc <= now:
            continue
        candidates.append(event)
    candidates.sort(key=lambda event: str(event.get("openDate") or ""))
    candidates = candidates[:max_events]

    schedule_cache: dict[str, Mapping[str, Any]] = {}
    props: list[dict[str, Any]] = []
    rejected_events: list[dict[str, Any]] = []
    rejected_props: list[dict[str, Any]] = []
    contract_unavailable = {PLAYER_HITS: 0, HITS_RUNS_RBI: 0, PITCHER_STRIKEOUTS: 0}
    matched_game_count = 0

    for event in candidates:
        source_event_id = _event_id(event)
        try:
            start_utc = _iso_utc(str(event.get("openDate") or ""))
            slate_date = start_utc.astimezone(EASTERN).date().isoformat()
            if slate_date not in schedule_cache:
                schedule_cache[slate_date] = dict(get_schedule(slate_date))
            event_props, event_rejections, event_unavailable = _normalize_event(
                event=event,
                schedule_payload=schedule_cache[slate_date],
                tab_fetcher=get_tab,
                players_fetcher=get_players,
                roster_fetcher=get_roster,
                slate_date=slate_date,
            )
            matched_game_count += 1
            props.extend(event_props)
            rejected_props.extend(event_rejections)
            for market_type, count in event_unavailable.items():
                contract_unavailable[market_type] += int(count)
        except Exception as exc:  # event-level fail-closed boundary
            rejected_events.append(
                {
                    "source_event_id": source_event_id or None,
                    "source_event_name": _event_name(event) or None,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )

    # Final global duplicate guard across all events. An exact identity should
    # never occur twice, even if an upstream event was duplicated.
    identity_counts: dict[tuple[int, int, str], int] = {}
    for prop in props:
        key = (int(prop["official_game_id"]), int(prop["official_player_id"]), str(prop["market_type"]))
        identity_counts[key] = identity_counts.get(key, 0) + 1
    duplicate_identities = {key for key, count in identity_counts.items() if count > 1}
    if duplicate_identities:
        props = [
            prop
            for prop in props
            if (int(prop["official_game_id"]), int(prop["official_player_id"]), str(prop["market_type"]))
            not in duplicate_identities
        ]
        for game_id, player_id, market_type in sorted(duplicate_identities):
            rejected_props.append(
                {
                    "official_game_id": game_id,
                    "official_player_id": player_id,
                    "market_type": market_type,
                    "reason": "duplicate_exact_identity_across_events",
                }
            )

    props.sort(key=lambda row: (row["official_game_id"], row["official_player_id"], row["market_type"]))
    return {
        "data_type": SNAPSHOT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "collected_at_utc": now.isoformat(),
        "provider": SOURCE,
        "transport": TRANSPORT,
        "http_methods": list(HTTP_METHODS),
        "sportsbook_region": FANDUEL_REGION,
        "landing_event_count": len(landing_events),
        "candidate_pregame_event_count": len(candidates),
        "matched_game_count": matched_game_count,
        "prop_count": len(props),
        "official_schedule_dates": sorted(schedule_cache),
        "props": props,
        "contract_unavailable_market_counts": contract_unavailable,
        "rejected_prop_count": len(rejected_props),
        "rejected_props": rejected_props,
        "rejected_event_count": len(rejected_events),
        "rejected_events": rejected_events,
        "player_name_matching_used": False,
        "fuzzy_matching_used": False,
    }


__all__ = [
    "HITS_RUNS_RBI",
    "HTTP_METHODS",
    "MLBPlayerPropCollectorError",
    "PITCHER_STRIKEOUTS",
    "PLAYER_HITS",
    "PROP_TABS",
    "SCHEMA_VERSION",
    "SNAPSHOT_DATA_TYPE",
    "SOURCE",
    "SUPPORTED_MARKET_TYPES",
    "TRANSPORT",
    "collect_live_mlb_player_props",
    "fetch_fanduel_event_players",
    "fetch_fanduel_event_prop_tab",
    "fetch_mlb_active_roster",
    "market_family",
    "normalize_two_way_player_market",
    "reconcile_fanduel_player_to_mlbam",
]
