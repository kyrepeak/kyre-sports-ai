"""WNBA Step 11C: read-only FanDuel live provider -> frozen Step-10 bridge.

This is the second sportsbook provider. It reads only FanDuel's anonymous US
sportsbook REST surface with the static public web key used by the FanDuel web
client, reconciles every event/player against official WNBA schedule + current
roster identity, pairs exact-line Over/Under player props, and emits the exact
frozen Step-10B ``flat_two_way_v1`` payload shape.

No login, cookies, wager placement, persistence, scheduler, Supabase write,
production activation, Step-8 projection change, or Step-9 calculation occurs.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import date as date_type, datetime, timezone
import hashlib
import json
import math
import os
import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

import httpx

from sports_api import wnba_step10_market_adapters as step10b
from sports_api import wnba_step10_release_freeze as step10_freeze
from sports_api.wnba_official_reconciliation import parse_official_schedule
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_step7g_first_party_rosters import get_first_party_current_players_dataset

SOURCE = "Kyre Sports API WNBA Step 11C FanDuel anonymous public live provider bridge"
SCHEMA_VERSION = "wnba_step_11c_fanduel_provider_bridge_v1"
MODEL_VERSION = "wnba_step11c_fanduel_official_identity_bridge_2026_regular_v1"
RELEASE_ID = "wnba_step11c_fanduel_provider_2026_regular_season_v1"
STEP11C_FANDUEL_PROVIDER_ENABLED_ENV = "WNBA_STEP11C_FANDUEL_PROVIDER_ENABLED"
STEP11B_FROZEN_HEAD_SHA = "26072ea38f3d540dc5771405e5c9df728a15f4ff"
STEP11A_FROZEN_HEAD_SHA = "695e7b45bd74fcb70c4f4fa6a886b4a054d06810"
STEP10_FROZEN_HEAD_SHA = "4341d178aa65806e9bc001c8759eccb4a003ea63"

PROVIDER = "FanDuel"
ADAPTER_TYPE = step10b.ADAPTER_FLAT_TWO_WAY_V1
FANDUEL_BASE_URL = "https://api.sportsbook.fanduel.com"
CONTENT_PAGE_PATH = "/sbapi/content-managed-page"
EVENT_PAGE_PATH = "/sbapi/event-page"
FANDUEL_PUBLIC_WEB_KEY = "FhMFpcPWXMeyZxOx"
FANDUEL_REGION = "NJ"
WNBA_CUSTOM_PAGE_ID = "wnba"
OFFICIAL_SCHEDULE_URL = "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json"
SUPPORTED_STATS = ("points", "rebounds", "assists", "pra")
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_RESPONSE_BYTES = 20_000_000
MAX_DISCOVERED_EVENTS = 20
MAX_RELEVANT_TABS_PER_EVENT = 8
MAX_RECORDS = 5_000
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SIDE_LINE_RE = re.compile(r"\b(over|under)\s*([0-9]+(?:\.[0-9]+)?)\b", re.I)

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep11FanDuelProviderDisabledError(RuntimeError):
    pass


class WNBAStep11FanDuelProviderNotReadyError(RuntimeError):
    pass


class WNBAStep11FanDuelProviderUpstreamError(RuntimeError):
    pass


class WNBAStep11FanDuelProviderIdentityError(ValueError):
    pass


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def step11c_fanduel_provider_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP11C_FANDUEL_PROVIDER_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [key for key in _OFF_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise WNBAStep11FanDuelProviderDisabledError(
            "Step 11C refuses production/scheduler/sync switches: " + ", ".join(bad)
        )
    if not step11c_fanduel_provider_enabled(source):
        raise WNBAStep11FanDuelProviderDisabledError(
            f"Step 11C requires {STEP11C_FANDUEL_PROVIDER_ENABLED_ENV}=true."
        )
    if not step10b.step10b_market_adapter_enabled(source):
        raise WNBAStep11FanDuelProviderDisabledError(
            "Step 11C requires frozen Step-10A/10B validation gates."
        )
    if step10_freeze.DEFAULT_ENABLED is not False or step10_freeze.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise WNBAStep11FanDuelProviderDisabledError(
            "Step 11C requires frozen Step 10 to remain default-OFF and production-disallowed."
        )


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _name_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _team_identity_key(value: Any) -> str:
    """Resolve exact official/sportsbook WNBA team aliases to one canonical key."""
    key = _name_key(value)
    if not key:
        return ""
    aliases: dict[str, str] = {}
    for team in get_wnba_teams():
        full_name = str(team["full_name"])
        abbreviation = str(team["abbreviation"])
        city = str(team["city"])
        nickname = str(team["nickname"])
        canonical = _name_key(full_name)
        city_initials = "".join(part[0] for part in re.findall(r"[A-Za-z0-9]+", city) if part)
        candidates = (
            full_name,
            f"{abbreviation} {nickname}",
            f"{city_initials} {nickname}" if city_initials else "",
        )
        for alias in candidates:
            alias_key = _name_key(alias)
            if not alias_key:
                continue
            previous = aliases.get(alias_key)
            if previous is not None and previous != canonical:
                raise WNBAStep11FanDuelProviderIdentityError("WNBA team alias registry is ambiguous.")
            aliases[alias_key] = canonical
    return aliases.get(key, key)


def _utc(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"WNBA {label} must be ISO-8601 with timezone.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"WNBA {label} must include timezone.")
    return parsed.astimezone(timezone.utc)


def _date(value: Any) -> str:
    text = str(value or "").strip()
    if not _DATE_RE.fullmatch(text):
        raise ValueError("WNBA slate_date must use YYYY-MM-DD.")
    date_type.fromisoformat(text)
    return text


def _headers() -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI/1.0; read-only)",
        "Origin": "https://sportsbook.fanduel.com",
        "Referer": "https://sportsbook.fanduel.com/",
        "x-sportsbook-region": FANDUEL_REGION,
    }


def _allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
        return False
    host = (parsed.hostname or "").casefold()
    return host in {"api.sportsbook.fanduel.com", "cdn.wnba.com"}


def _get_json(url: str, *, params: Mapping[str, Any] | None, requester: Callable[..., Any] | None, timeout: float) -> dict[str, Any]:
    if not _allowed_url(url):
        raise WNBAStep11FanDuelProviderUpstreamError("Step 11C refuses an unapproved network URL.")
    try:
        if requester is not None:
            response = requester(url, params=dict(params or {}), headers=_headers(), timeout=timeout)
        else:
            with httpx.Client(timeout=timeout, follow_redirects=False, headers=_headers()) as client:
                response = client.get(url, params=dict(params or {}))
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        raise WNBAStep11FanDuelProviderUpstreamError("Step 11C GET failed.") from exc
    if getattr(response, "status_code", None) != 200:
        raise WNBAStep11FanDuelProviderUpstreamError(
            f"Step 11C GET returned HTTP {getattr(response, 'status_code', 'unknown')}."
        )
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)) and len(content) > MAX_RESPONSE_BYTES:
        raise WNBAStep11FanDuelProviderUpstreamError("Step 11C response exceeded safety size limit.")
    try:
        payload = response.json()
    except Exception as exc:
        raise WNBAStep11FanDuelProviderUpstreamError("Step 11C endpoint returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise WNBAStep11FanDuelProviderUpstreamError("Step 11C endpoint returned non-object JSON.")
    return payload


def _iter_mapping_or_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        rows = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("_attachment_key", str(key))
                rows.append(row)
        return rows
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _event_id(event: Mapping[str, Any]) -> str:
    return _clean(event.get("eventId") or event.get("id") or event.get("_attachment_key"))


def _event_name(event: Mapping[str, Any]) -> str:
    return _clean(event.get("name") or event.get("eventName") or event.get("displayName"))


def _event_participants(event: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for field in ("homeTeam", "awayTeam"):
        value = event.get(field)
        if isinstance(value, Mapping):
            name = _clean(value.get("name") or value.get("fullName") or value.get("shortName"))
            if name:
                result.append(name)
        elif _clean(value):
            result.append(_clean(value))
    if len(result) >= 2:
        return result[:2]
    name = _event_name(event)
    for separator in (" @ ", " at ", " vs. ", " vs ", " v "):
        if separator.casefold() in name.casefold():
            parts = re.split(re.escape(separator), name, maxsplit=1, flags=re.I)
            if len(parts) == 2 and all(_clean(part) for part in parts):
                return [_clean(parts[0]), _clean(parts[1])]
    return result


def _event_date(event: Mapping[str, Any]) -> str | None:
    raw = event.get("openDate") or event.get("startTime") or event.get("startEventDate")
    if raw is None:
        return None
    try:
        return _utc(raw, "FanDuel event time").date().isoformat()
    except ValueError:
        return None


def _extract_events(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    attachments = document.get("attachments") or {}
    if not isinstance(attachments, Mapping):
        return []
    return _iter_mapping_or_list(attachments.get("events"))


def _extract_markets(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    attachments = document.get("attachments") or {}
    if not isinstance(attachments, Mapping):
        return []
    return _iter_mapping_or_list(attachments.get("markets"))


def _relevant_tab_ids(document: Mapping[str, Any]) -> list[str]:
    layout = document.get("layout") or {}
    if not isinstance(layout, Mapping):
        return []
    tabs = layout.get("tabs")
    rows = _iter_mapping_or_list(tabs)
    ids: list[str] = []
    for tab in rows:
        title = _clean(tab.get("title") or tab.get("name") or tab.get("displayName")).casefold()
        if not any(token in title for token in ("player points", "player rebounds", "player assists", "player combos", "player props")):
            continue
        tab_id = _clean(tab.get("id") or tab.get("tabId") or tab.get("_attachment_key"))
        if tab_id and tab_id not in ids:
            ids.append(tab_id)
    return ids[:MAX_RELEVANT_TABS_PER_EVENT]


def _roster_index(players: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(players, (str, bytes)) or not isinstance(players, Sequence) or not players:
        raise WNBAStep11FanDuelProviderIdentityError("Step 11C requires official WNBA roster rows.")
    index: dict[str, dict[str, Any]] = {}
    for raw in players:
        if not isinstance(raw, Mapping):
            raise WNBAStep11FanDuelProviderIdentityError("Official roster row must be an object.")
        name = _clean(raw.get("full_name") or raw.get("player_name"))
        key = _name_key(name)
        legacy_team_id = raw.get("team_id")
        official_team_id = raw.get("official_team_id")
        if legacy_team_id is not None and official_team_id is not None:
            try:
                legacy_team_id_int = int(legacy_team_id)
                official_team_id_int = int(official_team_id)
            except (TypeError, ValueError) as exc:
                raise WNBAStep11FanDuelProviderIdentityError("Official roster row lacks numeric identity.") from exc
            if legacy_team_id_int != official_team_id_int:
                raise WNBAStep11FanDuelProviderIdentityError(
                    "Official roster row has conflicting team identity fields."
                )
        team_id_source = legacy_team_id if legacy_team_id is not None else official_team_id
        try:
            player_id = int(raw.get("player_id")); team_id = int(team_id_source)
        except (TypeError, ValueError) as exc:
            raise WNBAStep11FanDuelProviderIdentityError("Official roster row lacks numeric identity.") from exc
        if not key or player_id <= 0 or team_id <= 0 or key in index:
            raise WNBAStep11FanDuelProviderIdentityError(f"Ambiguous/invalid official player identity {name!r}.")
        index[key] = {"player_id": player_id, "player_name": name, "team_id": team_id}
    return index


def _game_map(events: Sequence[Mapping[str, Any]], games: Sequence[Mapping[str, Any]], slate_date: str) -> dict[str, dict[str, Any]]:
    target = date_type.fromisoformat(slate_date)
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        eid = _event_id(event)
        participants = {_team_identity_key(name) for name in _event_participants(event) if _team_identity_key(name)}
        if not eid or len(participants) != 2:
            raise WNBAStep11FanDuelProviderIdentityError("FanDuel event lacks unique id/two team identities.")
        candidates = []
        for game in games:
            pair = {_team_identity_key(game.get("home_team_name")), _team_identity_key(game.get("away_team_name"))}
            if pair != participants:
                continue
            try:
                game_day = date_type.fromisoformat(str(game.get("game_date")))
            except ValueError:
                continue
            if abs((game_day - target).days) <= 1:
                candidates.append(dict(game))
        event_day = _event_date(event)
        if event_day:
            exact = [game for game in candidates if str(game.get("game_date")) == event_day]
            if exact:
                candidates = exact
        if len(candidates) != 1:
            raise WNBAStep11FanDuelProviderIdentityError(
                f"Step 11C requires one official WNBA game for FanDuel event {eid}; found {len(candidates)}."
            )
        result[eid] = candidates[0]
    return result


def _market_stat(market: Mapping[str, Any]) -> str | None:
    text = " ".join(_clean(market.get(key)) for key in ("marketName", "marketType", "name", "type")).casefold()
    compact = re.sub(r"[^a-z]+", " ", text)
    if all(token in compact for token in ("points", "rebounds", "assists")):
        return "pra"
    if "points rebounds assists" in compact or "pts rebs asts" in compact or "pts reb ast" in compact:
        return "pra"
    if "rebounds" in compact or re.search(r"\brebs?\b", compact):
        return "rebounds"
    if "assists" in compact or re.search(r"\basts?\b", compact):
        return "assists"
    if "points" in compact or re.search(r"\bpts?\b", compact):
        return "points"
    return None


def _runner_side_line(runner: Mapping[str, Any]) -> tuple[str, float] | None:
    name = _clean(runner.get("runnerName") or runner.get("name") or runner.get("selectionName"))
    match = _SIDE_LINE_RE.search(name)
    if match:
        return match.group(1).casefold(), round(float(match.group(2)), 6)
    side = _clean(runner.get("side") or runner.get("resultType")).casefold()
    if side not in {"over", "under"}:
        return None
    try:
        line = float(runner.get("handicap") if runner.get("handicap") is not None else runner.get("line"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(line):
        return None
    return side, round(line, 6)


def _declares_player_market(
    market: Mapping[str, Any],
    runners: Sequence[Mapping[str, Any]],
) -> bool:
    """Return True only when FanDuel explicitly supplies player-market evidence."""
    identity_fields = ("playerName", "participantName", "player")
    for key in identity_fields:
        if _clean(market.get(key)):
            return True
    for runner in runners:
        for key in identity_fields:
            if _clean(runner.get(key)):
                return True
    declaration = " ".join(
        _clean(market.get(key))
        for key in ("marketName", "marketType", "name", "type")
    )
    return bool(re.search(r"\bplayer\b", declaration, flags=re.I))


def _market_player_name(market: Mapping[str, Any], runners: Sequence[Mapping[str, Any]], stat: str) -> str:
    for key in ("playerName", "participantName", "player"):
        value = _clean(market.get(key))
        if value:
            return value
    for runner in runners:
        for key in ("playerName", "participantName", "player"):
            value = _clean(runner.get(key))
            if value:
                return value
    # Some FanDuel player markets put the player in the market title.
    title = _clean(market.get("marketName") or market.get("name"))
    generic = {
        "points": ("player points", "points"),
        "rebounds": ("player rebounds", "rebounds"),
        "assists": ("player assists", "assists"),
        "pra": ("player points + rebounds + assists", "points + rebounds + assists", "pra"),
    }[stat]
    candidate = title
    for suffix in sorted(generic, key=len, reverse=True):
        candidate = re.sub(rf"\s*[-–—:]?\s*{re.escape(suffix)}\s*$", "", candidate, flags=re.I)
    if candidate and _name_key(candidate) not in {_name_key(value) for value in generic}:
        return _clean(candidate)
    # Last fallback: remove Over/Under + line from a runner title.
    for runner in runners:
        name = _clean(runner.get("runnerName") or runner.get("name"))
        stripped = _SIDE_LINE_RE.sub("", name)
        stripped = re.sub(r"\s*[-–—:]\s*$", "", stripped).strip()
        if stripped and stripped.casefold() not in {"over", "under"}:
            return stripped
    return ""


def _american_price(runner: Mapping[str, Any]) -> int:
    odds = runner.get("winRunnerOdds") or {}
    if not isinstance(odds, Mapping):
        raise WNBAStep11FanDuelProviderIdentityError("FanDuel runner odds object missing.")
    american = odds.get("americanDisplayOdds") or {}
    if isinstance(american, Mapping) and american.get("americanOdds") is not None:
        try:
            price = int(american["americanOdds"])
        except (TypeError, ValueError) as exc:
            raise WNBAStep11FanDuelProviderIdentityError("FanDuel American odds malformed.") from exc
    else:
        true_odds = odds.get("trueOdds") or {}
        decimal_obj = true_odds.get("decimalOdds") if isinstance(true_odds, Mapping) else None
        value = decimal_obj.get("decimalOdds") if isinstance(decimal_obj, Mapping) else None
        try:
            decimal = float(value)
        except (TypeError, ValueError) as exc:
            raise WNBAStep11FanDuelProviderIdentityError("FanDuel runner has no usable price.") from exc
        if not math.isfinite(decimal) or decimal <= 1:
            raise WNBAStep11FanDuelProviderIdentityError("FanDuel decimal odds invalid.")
        price = int(round((decimal - 1) * 100)) if decimal >= 2 else int(round(-100 / (decimal - 1)))
    if abs(price) < 100 or abs(price) > 100_000:
        raise WNBAStep11FanDuelProviderIdentityError("FanDuel odds outside frozen Step-10 contract.")
    return price


def build_step11c_fanduel_provider_bridge(
    *,
    event_page_documents: Sequence[Mapping[str, Any]],
    official_schedule_document: Mapping[str, Any],
    official_roster_players: Sequence[Mapping[str, Any]],
    slate_date: str,
    evaluated_at: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Pure FanDuel normalization/reconciliation builder; performs no network call."""
    _assert_safe_environment(env)
    target_date = _date(slate_date)
    evaluated = _utc(evaluated_at or datetime.now(timezone.utc), "evaluated_at")
    if isinstance(event_page_documents, (str, bytes)) or not isinstance(event_page_documents, Sequence) or not event_page_documents:
        raise ValueError("Step 11C requires one or more event-page documents.")

    event_meta: dict[str, dict[str, Any]] = {}
    market_meta: dict[tuple[str, str], tuple[dict[str, Any], str]] = {}
    source_summary = []
    for entry in event_page_documents:
        if not isinstance(entry, Mapping) or set(entry) != {"event_id", "captured_at_utc", "document"}:
            raise ValueError("Step 11C event-page entries require exactly event_id, captured_at_utc, document.")
        eid = _clean(entry["event_id"])
        captured = _utc(entry["captured_at_utc"], "captured_at_utc").isoformat()
        doc = entry["document"]
        if not eid or not isinstance(doc, Mapping):
            raise ValueError("Step 11C event-page entry is malformed.")
        events = _extract_events(doc)
        matched_event = next((event for event in events if _event_id(event) == eid), None)
        if matched_event is not None:
            previous = event_meta.get(eid)
            if previous is not None and {_event_name(previous), tuple(_event_participants(previous))} != {_event_name(matched_event), tuple(_event_participants(matched_event))}:
                raise WNBAStep11FanDuelProviderIdentityError(f"Conflicting FanDuel event metadata for {eid}.")
            event_meta[eid] = dict(matched_event)
        for market in _extract_markets(doc):
            market_id = _clean(market.get("marketId") or market.get("id") or market.get("_attachment_key"))
            if not market_id:
                continue
            key = (eid, market_id)
            existing = market_meta.get(key)
            normalized = dict(market)
            if existing is not None and existing[0] != normalized:
                raise WNBAStep11FanDuelProviderIdentityError(f"Conflicting FanDuel market payload for {market_id}.")
            market_meta[key] = (normalized, captured)
        source_summary.append({"event_id": eid, "captured_at_utc": captured, "market_count": len(_extract_markets(doc))})

    if not event_meta:
        raise WNBAStep11FanDuelProviderNotReadyError("Step 11C event pages supplied no usable FanDuel event metadata.")
    games = parse_official_schedule(dict(official_schedule_document))
    roster = _roster_index(official_roster_players)
    game_by_event = _game_map(list(event_meta.values()), games, target_date)

    grouped: dict[tuple[str, int, str, float, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for (eid, market_id), (market, captured) in market_meta.items():
        stat = _market_stat(market)
        if stat not in SUPPORTED_STATS:
            continue
        status = _clean(market.get("marketStatus") or market.get("status")).casefold()
        if status and status not in {"open", "active"}:
            continue
        runners = _iter_mapping_or_list(market.get("runners"))
        player_name = _market_player_name(market, runners, stat)
        player = roster.get(_name_key(player_name))
        if player is None:
            # FanDuel exposes many team/game markets whose names contain words
            # such as "Points" (for example Race to 15 and Total Points).
            # They are not player props and must not enter player identity
            # reconciliation merely because _market_stat recognized a stat token.
            if not _declares_player_market(market, runners):
                continue
            raise WNBAStep11FanDuelProviderIdentityError(
                f"Step 11C could not uniquely map FanDuel player {player_name!r}."
            )
        game = game_by_event.get(eid)
        if game is None:
            raise WNBAStep11FanDuelProviderIdentityError(f"Unreconciled FanDuel event {eid}.")
        if int(player["team_id"]) not in {int(game["home_team_id"]), int(game["away_team_id"])}:
            raise WNBAStep11FanDuelProviderIdentityError(
                f"FanDuel player {player['player_name']!r} is not on either official game team."
            )
        for runner in runners:
            runner_status = _clean(runner.get("runnerStatus") or runner.get("status")).casefold()
            if runner_status and runner_status not in {"active", "open"}:
                continue
            side_line = _runner_side_line(runner)
            if side_line is None:
                continue
            side, line = side_line
            if not 0 <= line <= 250:
                raise WNBAStep11FanDuelProviderIdentityError("FanDuel line outside frozen Step-10 contract.")
            key = (str(game["game_id"]), int(player["player_id"]), stat, line, market_id)
            if side in grouped[key]:
                raise WNBAStep11FanDuelProviderIdentityError("Duplicate same-side FanDuel quote at one exact market/line.")
            grouped[key][side] = {
                "price": _american_price(runner),
                "captured": captured,
                "game": game,
                "player": player,
                "event_id": eid,
                "market_id": market_id,
                "selection_id": _clean(runner.get("selectionId") or runner.get("id") or runner.get("_attachment_key")),
            }

    records = []
    pair_evidence = []
    for key, sides in grouped.items():
        if set(sides) != {"over", "under"}:
            continue
        over, under = sides["over"], sides["under"]
        if over["captured"] != under["captured"]:
            raise WNBAStep11FanDuelProviderIdentityError("FanDuel Over/Under pair must share capture timestamp.")
        game_id, player_id, stat, line, market_id = key
        records.append({
            "game_id": game_id,
            "player_id": player_id,
            "player_name": over["player"]["player_name"],
            "sportsbook": PROVIDER,
            "stat": stat,
            "line": line,
            "over_price": over["price"],
            "under_price": under["price"],
            "market_captured_at": over["captured"],
        })
        pair_evidence.append({
            "game_id": game_id, "player_id": player_id, "stat": stat, "line": line,
            "source_event_id": over["event_id"], "source_market_id": market_id,
            "over_selection_id": over["selection_id"], "under_selection_id": under["selection_id"],
        })
    records.sort(key=lambda row: (row["game_id"], row["player_id"], row["stat"], row["line"]))
    pair_evidence.sort(key=lambda row: (row["game_id"], row["player_id"], row["stat"], row["line"]))
    if not records:
        raise WNBAStep11FanDuelProviderNotReadyError("Step 11C produced no complete official-identity two-way FanDuel records.")
    if len(records) > MAX_RECORDS:
        raise WNBAStep11FanDuelProviderNotReadyError("Step 11C record count exceeded safety limit.")

    payload = {"provider": PROVIDER, "price_format": "american", "records": records}
    adapted = step10b.adapt_step10b_market_payload(ADAPTER_TYPE, payload, evaluated_at=evaluated, env=env)
    result = {
        "data_type": "wnba_step11c_fanduel_provider_bridge",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "slate_date": target_date,
        "provider": PROVIDER,
        "public_surface": {
            "base_url": FANDUEL_BASE_URL,
            "content_page_path": CONTENT_PAGE_PATH,
            "event_page_path": EVENT_PAGE_PATH,
            "custom_page_id": WNBA_CUSTOM_PAGE_ID,
            "region": FANDUEL_REGION,
            "static_public_web_key_used": True,
        },
        "source_summary": source_summary,
        "identity": {
            "fanDuel_event_count": len(event_meta),
            "fanDuel_market_count": len(market_meta),
            "official_schedule_game_count": len(games),
            "official_roster_player_count": len(roster),
            "reconciled_event_count": len(game_by_event),
            "two_way_record_count": len(records),
            "pair_evidence": pair_evidence,
        },
        "provider_refresh": {"provider": PROVIDER, "adapter_type": ADAPTER_TYPE, "attempts": [{"ok": True, "payload": payload}]},
        "step10_validation": {
            "adapter_type": ADAPTER_TYPE,
            "step10b_schema_version": step10b.SCHEMA_VERSION,
            "step10b_model_version": step10b.MODEL_VERSION,
            "step10b_release_id": step10b.RELEASE_ID,
            "step10b_frozen_head_sha": step10_freeze.STEP10B_FROZEN_SHA,
            "adapter_content_sha256": adapted["adapter_content_sha256"],
            "step10a_snapshot_content_sha256": adapted["lineage"]["step10a_snapshot_content_sha256"],
            "record_count": adapted["adapter"]["output_record_count"],
        },
        "lineage": {
            "step11b_frozen_git_sha": STEP11B_FROZEN_HEAD_SHA,
            "step11a_frozen_git_sha": STEP11A_FROZEN_HEAD_SHA,
            "step10_frozen_git_sha": STEP10_FROZEN_HEAD_SHA,
            "step10a_frozen_git_sha": step10_freeze.STEP10A_FROZEN_SHA,
            "step10b_frozen_git_sha": step10_freeze.STEP10B_FROZEN_SHA,
        },
        "guardrails": {
            "sportsbook_network_fetch_performed": False,
            "official_wnba_network_fetch_performed": False,
            "sportsbook_http_methods": [],
            "authentication_used": False,
            "cookies_used": False,
            "wager_action_performed": False,
            "paid_odds_vendor_used": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9_called": False,
            "vig_removed": False,
            "edge_calculated": False,
            "expected_value_calculated": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    surface = dict(result); surface.pop("generated_at_utc", None)
    result["provider_bridge_content_sha256"] = _canonical_hash(surface)
    _assert_safe_environment(env)
    return result


def fetch_step11c_fanduel_provider_bridge(
    *,
    season: int,
    slate_date: str,
    evaluated_at: datetime | None = None,
    requester: Callable[..., Any] | None = None,
    roster_loader: Callable[[int], Mapping[str, Any]] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """GET FanDuel WNBA event/prop pages and build one Step-10 provider refresh object."""
    _assert_safe_environment(env)
    if int(season) != 2026:
        raise ValueError("Step 11C is certified for the 2026 Regular Season only.")
    target_date = _date(slate_date)
    evaluated = _utc(evaluated_at or datetime.now(timezone.utc), "evaluated_at")
    try:
        timeout = float(timeout_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("Step 11C timeout must be numeric.") from exc
    if not math.isfinite(timeout) or not 0.5 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError("Step 11C timeout must be from 0.5 through 60 seconds.")

    content_url = FANDUEL_BASE_URL + CONTENT_PAGE_PATH
    common = {"_ak": FANDUEL_PUBLIC_WEB_KEY, "page": "CUSTOM", "customPageId": WNBA_CUSTOM_PAGE_ID, "timezone": "America/New_York"}
    content = _get_json(content_url, params=common, requester=requester, timeout=timeout)
    discovered = _extract_events(content)
    target_events = []
    for event in discovered:
        event_day = _event_date(event)
        if event_day is None or event_day == target_date:
            target_events.append(event)
    if not target_events:
        raise WNBAStep11FanDuelProviderNotReadyError("FanDuel WNBA landing page exposed no target-slate events.")
    if len(target_events) > MAX_DISCOVERED_EVENTS:
        raise WNBAStep11FanDuelProviderNotReadyError("FanDuel event count exceeded Step 11C safety limit.")

    documents: list[dict[str, Any]] = []
    event_url = FANDUEL_BASE_URL + EVENT_PAGE_PATH
    sportsbook_get_count = 1
    for event in target_events:
        eid = _event_id(event)
        if not eid:
            raise WNBAStep11FanDuelProviderIdentityError("FanDuel content page returned event without id.")
        base_doc = _get_json(event_url, params={"_ak": FANDUEL_PUBLIC_WEB_KEY, "eventId": eid}, requester=requester, timeout=timeout)
        sportsbook_get_count += 1
        captured = datetime.now(timezone.utc).isoformat()
        documents.append({"event_id": eid, "captured_at_utc": captured, "document": base_doc})
        for tab_id in _relevant_tab_ids(base_doc):
            tab_doc = _get_json(event_url, params={"_ak": FANDUEL_PUBLIC_WEB_KEY, "eventId": eid, "tab": tab_id}, requester=requester, timeout=timeout)
            sportsbook_get_count += 1
            documents.append({"event_id": eid, "captured_at_utc": datetime.now(timezone.utc).isoformat(), "document": tab_doc})

    schedule_document = _get_json(OFFICIAL_SCHEDULE_URL, params=None, requester=requester, timeout=timeout)
    loader = roster_loader or (lambda requested_season: get_first_party_current_players_dataset(requested_season, current_roster_only=True))
    roster_dataset = loader(int(season))
    if not isinstance(roster_dataset, Mapping) or not isinstance(roster_dataset.get("players"), list):
        raise WNBAStep11FanDuelProviderUpstreamError("Step 11C official roster loader returned invalid dataset.")

    result = build_step11c_fanduel_provider_bridge(
        event_page_documents=documents,
        official_schedule_document=schedule_document,
        official_roster_players=roster_dataset["players"],
        slate_date=target_date,
        evaluated_at=evaluated,
        env=env,
    )
    result = deepcopy(result)
    result["network"] = {
        "sportsbook_get_count": sportsbook_get_count,
        "official_schedule_get_count": 1,
        "http_methods": ["GET"],
        "redirects_followed": False,
        "authentication_used": False,
        "cookies_used": False,
        "static_public_web_key_used": True,
    }
    result["guardrails"]["sportsbook_network_fetch_performed"] = True
    result["guardrails"]["official_wnba_network_fetch_performed"] = True
    result["guardrails"]["sportsbook_http_methods"] = ["GET"]
    surface = dict(result); surface.pop("generated_at_utc", None); surface.pop("provider_bridge_content_sha256", None)
    result["provider_bridge_content_sha256"] = _canonical_hash(surface)
    _assert_safe_environment(env)
    return result
