"""WNBA Step 11A: read-only DraftKings live provider -> frozen Step-10 bridge.

This is the first post-Step-10 layer allowed to perform sportsbook HTTP GETs.
It reads only the four previously verified public DraftKings WNBA player-prop
JSON endpoints, reconciles DraftKings event/player identity against official
WNBA schedule + current roster identity, pairs exact-line Over/Under markets,
and emits the exact frozen Step-10B ``flat_two_way_v1`` payload shape.

Step 10 remains immutable and default-OFF. This module never logs in, uses
cookies, places wagers, writes Supabase/persistence, starts a scheduler, enables
production runtime, or changes any basketball/model probability surface.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import date as date_type, datetime, timedelta, timezone
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
from sports_api.collectors.wnba_draftkings_direct import normalize_draftkings_document
from sports_api.wnba_official_reconciliation import (
    extract_draftkings_events,
    parse_official_schedule,
)
from sports_api.wnba_step7g_first_party_rosters import (
    get_first_party_current_players_dataset,
)

SOURCE = "Kyre Sports API WNBA Step 11A DraftKings public live provider bridge"
SCHEMA_VERSION = "wnba_step_11a_draftkings_provider_bridge_v1"
MODEL_VERSION = "wnba_step11a_draftkings_official_identity_bridge_2026_regular_v1"
RELEASE_ID = "wnba_step11a_draftkings_provider_2026_regular_season_v1"
STEP11A_DRAFTKINGS_PROVIDER_ENABLED_ENV = "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED"
STEP10_FROZEN_SHA = "4341d178aa65806e9bc001c8759eccb4a003ea63"

OFFICIAL_SCHEDULE_URL = "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json"
FROZEN_DRAFTKINGS_ENDPOINTS = (
    "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusva/v1/leagues/94682/categories/1215/subcategories/12488",
    "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusva/v1/leagues/94682/categories/1216/subcategories/12492",
    "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusva/v1/leagues/94682/categories/1217/subcategories/12495",
    "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusva/v1/leagues/94682/categories/583/subcategories/5001",
)
PROVIDER = "DraftKings"
ADAPTER_TYPE = step10b.ADAPTER_FLAT_TWO_WAY_V1
SUPPORTED_STATS = ("points", "rebounds", "assists", "pra")
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_RESPONSE_BYTES = 15_000_000
MAX_NORMALIZED_OFFERS = 10_000
MAX_RECORDS = 5_000
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep11DraftKingsProviderDisabledError(RuntimeError):
    """Raised when Step 11A is not explicitly enabled or isolation is unsafe."""


class WNBAStep11DraftKingsProviderNotReadyError(RuntimeError):
    """Raised when current market/identity evidence cannot form safe two-way records."""


class WNBAStep11DraftKingsProviderUpstreamError(RuntimeError):
    """Raised when a public DraftKings/WNBA GET fails or returns malformed data."""


class WNBAStep11DraftKingsProviderIdentityError(ValueError):
    """Raised when a sportsbook market cannot be mapped uniquely to official WNBA identity."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step11a_draftkings_provider_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP11A_DRAFTKINGS_PROVIDER_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep11DraftKingsProviderDisabledError(
            "Step 11A refuses production/scheduler/sync switches: " + ", ".join(bad)
        )
    if not _truthy(source.get(STEP11A_DRAFTKINGS_PROVIDER_ENABLED_ENV)):
        raise WNBAStep11DraftKingsProviderDisabledError(
            f"Step 11A requires {STEP11A_DRAFTKINGS_PROVIDER_ENABLED_ENV}=true."
        )
    if not step10b.step10b_market_adapter_enabled(source):
        raise WNBAStep11DraftKingsProviderDisabledError(
            "Step 11A requires the frozen Step-10A/10B validation gates to be explicitly enabled."
        )
    if step10_freeze.DEFAULT_ENABLED is not False:
        raise WNBAStep11DraftKingsProviderDisabledError(
            "Step 11A requires frozen Step 10 to remain default-OFF."
        )
    if step10_freeze.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise WNBAStep11DraftKingsProviderDisabledError(
            "Step 11A requires frozen Step 10 production activation to remain disallowed."
        )


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _name_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _date(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not _DATE_RE.fullmatch(text):
        raise ValueError(f"WNBA {label} must use YYYY-MM-DD.")
    return text


def _utc(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"WNBA {label} must be ISO-8601 with timezone.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"WNBA {label} must include a timezone offset.")
    return parsed.astimezone(timezone.utc)


def _timeout(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("WNBA Step 11A timeout must be numeric.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("WNBA Step 11A timeout must be numeric.") from exc
    if not math.isfinite(result) or not 0.5 <= result <= MAX_TIMEOUT_SECONDS:
        raise ValueError(
            f"WNBA Step 11A timeout must be from 0.5 through {MAX_TIMEOUT_SECONDS:g} seconds."
        )
    return result


def _allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold()
    if parsed.scheme.casefold() != "https" or parsed.username or parsed.password or parsed.fragment:
        return False
    return url in FROZEN_DRAFTKINGS_ENDPOINTS or url == OFFICIAL_SCHEDULE_URL or host.endswith(".wnba.com")


def _headers(url: str) -> dict[str, str]:
    host = (urlparse(url).hostname or "").casefold()
    if host.endswith("draftkings.com"):
        return {
            "Accept": "application/json",
            "User-Agent": "kyre-sports-api/wnba-step11a (+read-only-market-research)",
            "Referer": "https://sportsbook.draftkings.com/leagues/basketball/wnba",
        }
    return {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI/1.0)",
        "Referer": "https://www.wnba.com/",
    }


def _get_json(
    url: str,
    *,
    requester: Callable[..., Any] | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    if not _allowed_url(url):
        raise WNBAStep11DraftKingsProviderUpstreamError(
            "Step 11A refuses an unapproved network URL."
        )
    try:
        if requester is not None:
            try:
                response = requester(url, headers=_headers(url), timeout=timeout_seconds)
            except TypeError:
                response = requester("GET", url, headers=_headers(url), timeout=timeout_seconds)
        else:
            with httpx.Client(
                timeout=timeout_seconds,
                follow_redirects=False,
                headers=_headers(url),
            ) as client:
                response = client.get(url)
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        raise WNBAStep11DraftKingsProviderUpstreamError(
            f"Step 11A GET failed for {(urlparse(url).hostname or 'unknown')}."
        ) from exc
    status = getattr(response, "status_code", None)
    if status != 200:
        raise WNBAStep11DraftKingsProviderUpstreamError(
            f"Step 11A GET returned HTTP {status if status is not None else 'unknown'}."
        )
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)) and len(content) > MAX_RESPONSE_BYTES:
        raise WNBAStep11DraftKingsProviderUpstreamError(
            f"Step 11A response exceeded {MAX_RESPONSE_BYTES} bytes."
        )
    try:
        document = response.json()
    except Exception as exc:
        raise WNBAStep11DraftKingsProviderUpstreamError(
            "Step 11A endpoint returned invalid JSON."
        ) from exc
    if not isinstance(document, dict):
        raise WNBAStep11DraftKingsProviderUpstreamError(
            "Step 11A endpoint returned a non-object JSON payload."
        )
    return document


def _american_price(offer: Mapping[str, Any]) -> int:
    value = offer.get("american_odds")
    if value is not None:
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise WNBAStep11DraftKingsProviderIdentityError(
                "Step 11A received malformed American odds."
            ) from exc
        if abs(result) < 100 or abs(result) > 100_000:
            raise WNBAStep11DraftKingsProviderIdentityError(
                "Step 11A received American odds outside the frozen Step-10 contract."
            )
        return result
    try:
        decimal = float(offer.get("decimal_odds"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep11DraftKingsProviderIdentityError(
            "Step 11A offer has no usable price."
        ) from exc
    if not math.isfinite(decimal) or decimal <= 1.0:
        raise WNBAStep11DraftKingsProviderIdentityError(
            "Step 11A offer has invalid decimal odds."
        )
    result = int(round((decimal - 1.0) * 100.0)) if decimal >= 2.0 else int(round(-100.0 / (decimal - 1.0)))
    if abs(result) < 100 or abs(result) > 100_000:
        raise WNBAStep11DraftKingsProviderIdentityError(
            "Step 11A decimal odds convert outside the frozen Step-10 contract."
        )
    return result


def _roster_index(players: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(players, (str, bytes)) or not isinstance(players, Sequence) or not players:
        raise WNBAStep11DraftKingsProviderIdentityError(
            "Step 11A requires nonempty official WNBA roster rows."
        )
    index: dict[str, dict[str, Any]] = {}
    for raw in players:
        if not isinstance(raw, Mapping):
            raise WNBAStep11DraftKingsProviderIdentityError(
                "Step 11A official roster rows must be objects."
            )
        player_name = _clean(raw.get("full_name") or raw.get("player_name"))
        key = _name_key(player_name)
        legacy_team_id = raw.get("team_id")
        official_team_id = raw.get("official_team_id")
        if legacy_team_id is not None and official_team_id is not None:
            try:
                legacy_team_id_int = int(legacy_team_id)
                official_team_id_int = int(official_team_id)
            except (TypeError, ValueError) as exc:
                raise WNBAStep11DraftKingsProviderIdentityError(
                    "Step 11A official roster row is missing numeric player/team identity."
                ) from exc
            if legacy_team_id_int != official_team_id_int:
                raise WNBAStep11DraftKingsProviderIdentityError(
                    "Step 11A official roster row has conflicting team identity fields."
                )
        team_id_source = legacy_team_id if legacy_team_id is not None else official_team_id
        try:
            player_id = int(raw.get("player_id"))
            team_id = int(team_id_source)
        except (TypeError, ValueError) as exc:
            raise WNBAStep11DraftKingsProviderIdentityError(
                "Step 11A official roster row is missing numeric player/team identity."
            ) from exc
        if not key or player_id <= 0 or team_id <= 0:
            raise WNBAStep11DraftKingsProviderIdentityError(
                "Step 11A official roster row has invalid identity."
            )
        if key in index:
            raise WNBAStep11DraftKingsProviderIdentityError(
                f"Step 11A found ambiguous official player name {player_name!r}."
            )
        index[key] = {
            "player_id": player_id,
            "player_name": player_name,
            "team_id": team_id,
            "team_key": _clean(raw.get("team_key")),
        }
    return index


def _event_game_map(
    events: Sequence[Mapping[str, Any]],
    games: Sequence[Mapping[str, Any]],
    *,
    slate_date: str,
) -> dict[str, dict[str, Any]]:
    if not games:
        raise WNBAStep11DraftKingsProviderIdentityError(
            "Step 11A official schedule contains no parseable games."
        )
    target = date_type.fromisoformat(slate_date)
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        event_id = _clean(event.get("source_event_id"))
        if not event_id:
            continue
        participant_keys = {
            _name_key(name) for name in (event.get("participants") or []) if _name_key(name)
        }
        if len(participant_keys) < 2:
            raise WNBAStep11DraftKingsProviderIdentityError(
                f"Step 11A DraftKings event {event_id} lacks two team identities."
            )
        candidates: list[dict[str, Any]] = []
        for game in games:
            pair = {
                _name_key(game.get("home_team_name")),
                _name_key(game.get("away_team_name")),
            }
            if pair != participant_keys:
                continue
            try:
                game_day = date_type.fromisoformat(str(game.get("game_date")))
            except ValueError:
                continue
            if abs((game_day - target).days) <= 1:
                candidates.append(dict(game))
        event_date = _clean(event.get("event_date"))
        if event_date and _DATE_RE.fullmatch(event_date):
            exact = [game for game in candidates if str(game.get("game_date")) == event_date]
            if exact:
                candidates = exact
        if len(candidates) != 1:
            raise WNBAStep11DraftKingsProviderIdentityError(
                f"Step 11A requires one official game for DraftKings event {event_id}; found {len(candidates)}."
            )
        result[event_id] = candidates[0]
    return result


def _normalize_documents(
    documents: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if isinstance(documents, (str, bytes)) or not isinstance(documents, Sequence):
        raise ValueError("WNBA Step 11A draftkings_documents must be a sequence.")
    if len(documents) != len(FROZEN_DRAFTKINGS_ENDPOINTS):
        raise ValueError("WNBA Step 11A requires exactly the four frozen DraftKings endpoint documents.")
    expected = set(FROZEN_DRAFTKINGS_ENDPOINTS)
    seen_urls: set[str] = set()
    offers: list[dict[str, Any]] = []
    events_by_id: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for row in documents:
        if not isinstance(row, Mapping):
            raise ValueError("WNBA Step 11A document entries must be objects.")
        if set(row) != {"url", "captured_at_utc", "document"}:
            raise ValueError(
                "WNBA Step 11A document entries require exactly url, captured_at_utc, document."
            )
        url = str(row["url"])
        if url not in expected or url in seen_urls:
            raise ValueError("WNBA Step 11A documents must contain each frozen DraftKings URL exactly once.")
        seen_urls.add(url)
        captured = _utc(row["captured_at_utc"], "captured_at_utc").isoformat()
        document = row["document"]
        if not isinstance(document, Mapping):
            raise WNBAStep11DraftKingsProviderUpstreamError(
                "Step 11A DraftKings document must be a JSON object."
            )
        normalized = normalize_draftkings_document(dict(document), captured_at_utc=captured)
        offers.extend(normalized)
        for event in extract_draftkings_events(dict(document)):
            event_id = _clean(event.get("source_event_id"))
            if not event_id:
                continue
            existing = events_by_id.get(event_id)
            if existing is None:
                events_by_id[event_id] = dict(event)
            elif existing != dict(event):
                raise WNBAStep11DraftKingsProviderIdentityError(
                    f"Step 11A found conflicting metadata for DraftKings event {event_id}."
                )
        sources.append({
            "url": url,
            "captured_at_utc": captured,
            "normalized_offer_count": len(normalized),
        })
    if seen_urls != expected:
        raise ValueError("WNBA Step 11A did not receive the exact frozen endpoint set.")
    if not offers:
        raise WNBAStep11DraftKingsProviderNotReadyError(
            "Step 11A DraftKings endpoints returned no supported WNBA offers."
        )
    if len(offers) > MAX_NORMALIZED_OFFERS:
        raise WNBAStep11DraftKingsProviderNotReadyError(
            "Step 11A normalized offer count exceeded the safety limit."
        )
    deduped: list[dict[str, Any]] = []
    seen_offer_ids: set[str] = set()
    for offer in offers:
        key = _clean(offer.get("source_offer_id")) or _canonical_hash(offer)
        if key in seen_offer_ids:
            continue
        seen_offer_ids.add(key)
        deduped.append(dict(offer))
    return deduped, list(events_by_id.values()), sources


def build_step11a_draftkings_provider_bridge(
    *,
    draftkings_documents: Sequence[Mapping[str, Any]],
    official_schedule_document: Mapping[str, Any],
    official_roster_players: Sequence[Mapping[str, Any]],
    slate_date: str,
    evaluated_at: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Pure reconciliation builder. No network call occurs in this function."""
    _assert_safe_environment(env)
    target_date = _date(slate_date, "slate_date")
    evaluated = _utc(evaluated_at or datetime.now(timezone.utc), "evaluated_at")
    offers, events, sources = _normalize_documents(draftkings_documents)
    if not isinstance(official_schedule_document, Mapping):
        raise WNBAStep11DraftKingsProviderIdentityError(
            "Step 11A official schedule document must be an object."
        )
    games = parse_official_schedule(dict(official_schedule_document))
    roster = _roster_index(official_roster_players)
    event_games = _event_game_map(events, games, slate_date=target_date)

    grouped: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for offer in offers:
        stat = _clean(offer.get("stat")).casefold()
        side = _clean(offer.get("side")).casefold()
        if stat not in SUPPORTED_STATS or side not in {"over", "under"}:
            continue
        event_id = _clean(offer.get("source_event_id"))
        game = event_games.get(event_id)
        if game is None:
            raise WNBAStep11DraftKingsProviderIdentityError(
                f"Step 11A offer references unreconciled DraftKings event {event_id!r}."
            )
        player_key = _name_key(offer.get("player_name"))
        player = roster.get(player_key)
        if player is None:
            raise WNBAStep11DraftKingsProviderIdentityError(
                f"Step 11A could not uniquely map DraftKings player {offer.get('player_name')!r}."
            )
        allowed_team_ids = {int(game["home_team_id"]), int(game["away_team_id"])}
        if int(player["team_id"]) not in allowed_team_ids:
            raise WNBAStep11DraftKingsProviderIdentityError(
                f"Step 11A player {player['player_name']!r} is not on either team in official game {game['game_id']}."
            )
        try:
            line = round(float(offer.get("line")), 6)
        except (TypeError, ValueError) as exc:
            raise WNBAStep11DraftKingsProviderIdentityError("Step 11A offer line is invalid.") from exc
        if not math.isfinite(line) or not 0.0 <= line <= 250.0:
            raise WNBAStep11DraftKingsProviderIdentityError("Step 11A offer line is outside the Step-10 contract.")
        captured = _utc(offer.get("market_captured_at_utc"), "market_captured_at_utc").isoformat()
        key = (
            str(game["game_id"]),
            int(player["player_id"]),
            stat,
            line,
        )
        if side in grouped[key]:
            raise WNBAStep11DraftKingsProviderIdentityError(
                "Step 11A refuses duplicate same-side DraftKings quotes for one official game/player/stat/line."
            )
        grouped[key][side] = {
            "price": _american_price(offer),
            "captured_at_utc": captured,
            "source_event_id": event_id,
            "source_market_id": _clean(offer.get("source_market_id")),
            "source_offer_id": _clean(offer.get("source_offer_id")),
            "player": player,
            "game": game,
        }

    records: list[dict[str, Any]] = []
    pair_evidence: list[dict[str, Any]] = []
    for key, sides in grouped.items():
        if set(sides) != {"over", "under"}:
            raise WNBAStep11DraftKingsProviderNotReadyError(
                "Step 11A refuses incomplete DraftKings Over/Under pairs."
            )
        over = sides["over"]
        under = sides["under"]
        if over["source_market_id"] != under["source_market_id"]:
            raise WNBAStep11DraftKingsProviderIdentityError(
                "Step 11A refuses Over/Under sides from different DraftKings markets at the same official identity."
            )
        if over["captured_at_utc"] != under["captured_at_utc"]:
            raise WNBAStep11DraftKingsProviderIdentityError(
                "Step 11A requires Over/Under sides to share one capture timestamp."
            )
        game_id, player_id, stat, line = key
        record = {
            "game_id": game_id,
            "player_id": player_id,
            "player_name": over["player"]["player_name"],
            "sportsbook": PROVIDER,
            "stat": stat,
            "line": line,
            "over_price": over["price"],
            "under_price": under["price"],
            "market_captured_at": over["captured_at_utc"],
        }
        records.append(record)
        pair_evidence.append({
            "game_id": game_id,
            "player_id": player_id,
            "stat": stat,
            "line": line,
            "source_event_id": over["source_event_id"],
            "source_market_id": over["source_market_id"],
            "over_source_offer_id": over["source_offer_id"],
            "under_source_offer_id": under["source_offer_id"],
        })
    records.sort(key=lambda row: (
        row["game_id"], row["player_id"], row["stat"], row["line"]
    ))
    pair_evidence.sort(key=lambda row: (
        row["game_id"], row["player_id"], row["stat"], row["line"]
    ))
    if not records:
        raise WNBAStep11DraftKingsProviderNotReadyError(
            "Step 11A produced no complete official-identity two-way DraftKings records."
        )
    if len(records) > MAX_RECORDS:
        raise WNBAStep11DraftKingsProviderNotReadyError(
            "Step 11A record count exceeded the Step-10 safety limit."
        )

    payload = {
        "provider": PROVIDER,
        "price_format": "american",
        "records": records,
    }
    adapted = step10b.adapt_step10b_market_payload(
        ADAPTER_TYPE,
        payload,
        evaluated_at=evaluated,
        env=env,
    )
    provider_refresh = {
        "provider": PROVIDER,
        "adapter_type": ADAPTER_TYPE,
        "attempts": [{"ok": True, "payload": payload}],
    }
    result = {
        "data_type": "wnba_step11a_draftkings_provider_bridge",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "slate_date": target_date,
        "provider": PROVIDER,
        "frozen_endpoints": list(FROZEN_DRAFTKINGS_ENDPOINTS),
        "source_summary": sources,
        "identity": {
            "normalized_offer_count": len(offers),
            "draftkings_event_count": len(events),
            "official_schedule_game_count": len(games),
            "official_roster_player_count": len(roster),
            "reconciled_event_count": len(event_games),
            "two_way_record_count": len(records),
            "pair_evidence": pair_evidence,
        },
        "provider_refresh": provider_refresh,
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
            "step10_release_id": step10_freeze.RELEASE_ID,
            "step10_frozen_git_sha": STEP10_FROZEN_SHA,
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
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["provider_bridge_content_sha256"] = _canonical_hash(surface)
    _assert_safe_environment(env)
    return result


def fetch_step11a_draftkings_provider_bridge(
    *,
    season: int,
    slate_date: str,
    evaluated_at: datetime | None = None,
    requester: Callable[..., Any] | None = None,
    roster_loader: Callable[[int], Mapping[str, Any]] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Perform bounded GET-only market/identity reads and build a Step-10 refresh entry."""
    _assert_safe_environment(env)
    if int(season) != 2026:
        raise ValueError("WNBA Step 11A is certified for the 2026 Regular Season only.")
    target_date = _date(slate_date, "slate_date")
    evaluated = _utc(evaluated_at or datetime.now(timezone.utc), "evaluated_at")
    timeout = _timeout(timeout_seconds)

    schedule_document = _get_json(
        OFFICIAL_SCHEDULE_URL,
        requester=requester,
        timeout_seconds=timeout,
    )
    documents: list[dict[str, Any]] = []
    for url in FROZEN_DRAFTKINGS_ENDPOINTS:
        document = _get_json(url, requester=requester, timeout_seconds=timeout)
        documents.append({
            "url": url,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "document": document,
        })

    loader = roster_loader or (
        lambda requested_season: get_first_party_current_players_dataset(
            requested_season,
            current_roster_only=True,
        )
    )
    roster_dataset = loader(int(season))
    if not isinstance(roster_dataset, Mapping) or not isinstance(roster_dataset.get("players"), list):
        raise WNBAStep11DraftKingsProviderUpstreamError(
            "Step 11A official roster loader returned an invalid dataset."
        )
    if roster_loader is None:
        verification = roster_dataset.get("verification") or {}
        required_roster_guards = (
            "all_registered_teams_loaded",
            "all_players_have_official_wnba_player_ids",
            "player_ids_unique_across_teams",
            "rendered_tiles_match_react_flight_identity",
            "current_membership_from_official_team_roster_pages",
        )
        if not all(verification.get(key) is True for key in required_roster_guards):
            raise WNBAStep11DraftKingsProviderUpstreamError(
                "Step 11A first-party WNBA roster verification is incomplete."
            )

    result = build_step11a_draftkings_provider_bridge(
        draftkings_documents=documents,
        official_schedule_document=schedule_document,
        official_roster_players=roster_dataset["players"],
        slate_date=target_date,
        evaluated_at=evaluated,
        env=env,
    )
    result = deepcopy(result)
    result["network"] = {
        "sportsbook_get_count": len(FROZEN_DRAFTKINGS_ENDPOINTS),
        "official_schedule_get_count": 1,
        "official_roster_source_count": len(roster_dataset.get("team_source_urls") or {}),
        "http_methods": ["GET"],
        "redirects_followed": False,
        "authentication_used": False,
        "cookies_used": False,
    }
    result["guardrails"]["sportsbook_network_fetch_performed"] = True
    result["guardrails"]["official_wnba_network_fetch_performed"] = True
    result["guardrails"]["sportsbook_http_methods"] = ["GET"]
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    surface.pop("provider_bridge_content_sha256", None)
    result["provider_bridge_content_sha256"] = _canonical_hash(surface)
    _assert_safe_environment(env)
    return result
