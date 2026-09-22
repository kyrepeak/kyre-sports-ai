"""WNBA Step 6D direct DraftKings market collection.

This collector removes the paid-odds-vendor hop for the first active sportsbook.
It performs GET-only requests to explicitly configured, publicly reachable
DraftKings sportsbook JSON endpoints, normalizes supported WNBA player props to
Kyre's canonical offer schema, atomically publishes the result into the
Step-6C Kyre-owned durable feed, and returns the frozen Step-5O collection shape.

Safety and integrity rules:
- no DraftKings login, account credentials, cookies, wager placement, or browser automation;
- only HTTPS draftkings.com hosts are accepted;
- endpoint URLs must be explicitly configured because DraftKings internal IDs
  and paths are unofficial and can change;
- raw market values are never inferred from model projections;
- unsupported/malformed markets are ignored rather than guessed;
- frozen Step 5M remains the roster/slate/market-integrity authority.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from sports_api.collectors.wnba_kyre_market_feed import (
    SCHEMA_VERSION as KYRE_FEED_SCHEMA_VERSION,
    write_kyre_market_feed,
)
from sports_api.collectors.wnba_prop_feed_collector import (
    WNBAPropFeedCollectorModelInputError,
    WNBAPropFeedCollectorNotReadyError,
    WNBAPropFeedCollectorUpstreamError,
)
from sports_api.wnba_prop_line_feed_adapter import CANONICAL_FEED_FORMAT

MODEL_SOURCE = "Kyre Sports API WNBA Step 6D direct DraftKings collector"
MODEL_VERSION = "wnba_step_6d_direct_draftkings_v1"
SCHEMA_VERSION = MODEL_VERSION

DRAFTKINGS_PROVIDER_ID = "draftkings_direct"
DRAFTKINGS_URLS_ENV = "WNBA_DRAFTKINGS_MARKET_URLS_JSON"
DRAFTKINGS_TIMEOUT_ENV = "WNBA_DRAFTKINGS_REQUEST_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_URLS = 24
MAX_RESPONSE_BYTES = 15_000_000
DEFAULT_USER_AGENT = "kyre-sports-api/wnba-step6d (+market-research; GET-only)"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NUMBER_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d)")


class WNBADraftKingsDirectModelInputError(WNBAPropFeedCollectorModelInputError):
    pass


class WNBADraftKingsDirectNotReadyError(WNBAPropFeedCollectorNotReadyError):
    pass


class WNBADraftKingsDirectUpstreamError(WNBAPropFeedCollectorUpstreamError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _now().isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _allowed_draftkings_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold()
    return (
        parsed.scheme.casefold() == "https"
        and bool(host)
        and (host == "draftkings.com" or host.endswith(".draftkings.com"))
        and parsed.username is None
        and parsed.password is None
        and parsed.fragment == ""
    )


def resolve_draftkings_urls(
    urls: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    environment = _environment(env)
    if urls is None:
        raw = _clean(environment.get(DRAFTKINGS_URLS_ENV))
        if not raw:
            raise WNBADraftKingsDirectNotReadyError(
                f"Step 6D requires {DRAFTKINGS_URLS_ENV} as a JSON array of exact public DraftKings market URLs."
            )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WNBADraftKingsDirectModelInputError(
                f"{DRAFTKINGS_URLS_ENV} must be valid JSON."
            ) from exc
        if not isinstance(parsed, list):
            raise WNBADraftKingsDirectModelInputError(
                f"{DRAFTKINGS_URLS_ENV} must be a JSON array."
            )
        urls = parsed
    if not isinstance(urls, Sequence) or isinstance(urls, (str, bytes)):
        raise WNBADraftKingsDirectModelInputError("DraftKings URLs must be a sequence of strings.")
    result: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        text = _clean(raw)
        if not text:
            raise WNBADraftKingsDirectModelInputError("DraftKings URL entries cannot be empty.")
        if not _allowed_draftkings_url(text):
            raise WNBADraftKingsDirectModelInputError(
                "Step 6D accepts HTTPS draftkings.com URLs only and does not accept embedded credentials or fragments."
            )
        if text not in seen:
            result.append(text)
            seen.add(text)
    if not result:
        raise WNBADraftKingsDirectNotReadyError("No DraftKings URLs were configured.")
    if len(result) > MAX_URLS:
        raise WNBADraftKingsDirectModelInputError(f"Step 6D supports at most {MAX_URLS} DraftKings URLs per cycle.")
    return result


def _timeout(env: Mapping[str, str]) -> float:
    raw = _clean(env.get(DRAFTKINGS_TIMEOUT_ENV))
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError as exc:
        raise WNBADraftKingsDirectModelInputError(f"{DRAFTKINGS_TIMEOUT_ENV} must be numeric.") from exc
    if not 0.5 <= value <= MAX_TIMEOUT_SECONDS:
        raise WNBADraftKingsDirectModelInputError(
            f"{DRAFTKINGS_TIMEOUT_ENV} must be between 0.5 and {MAX_TIMEOUT_SECONDS} seconds."
        )
    return value


def describe_draftkings_direct_onboarding(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _environment(env)
    try:
        urls = resolve_draftkings_urls(env=environment)
        timeout = _timeout(environment)
        error = None
        ready = True
    except (WNBADraftKingsDirectNotReadyError, WNBADraftKingsDirectModelInputError) as exc:
        urls = []
        timeout = DEFAULT_TIMEOUT_SECONDS
        error = str(exc)
        ready = False
    return {
        "provider_id": DRAFTKINGS_PROVIDER_ID,
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "ready": ready,
        "configured_url_count": len(urls),
        "request_timeout_seconds": timeout,
        "configuration_error": error,
        "secret_required": False,
        "authentication_used": False,
        "cookies_used": False,
        "http_method": "GET",
        "allowed_host_suffix": "draftkings.com",
        "semantics": {
            "public_endpoint_only": True,
            "explicit_endpoint_configuration_required": True,
            "no_wager_actions": True,
            "no_login_or_account_session": True,
            "unofficial_endpoint_may_change": True,
            "step_5m_remains_market_integrity_authority": True,
        },
    }


def draftkings_direct_ready(env: Mapping[str, str] | None = None) -> bool:
    return bool(describe_draftkings_direct_onboarding(env).get("ready"))


def _american_odds(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("american") or value.get("americanOdds")
    text = _clean(value)
    if not text:
        return None
    text = text.replace("−", "-").replace("–", "-").replace("+", "").replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return None
    if not number.is_integer():
        return None
    integer = int(number)
    return integer if 100 <= abs(integer) <= 100_000 else None


def _decimal_odds(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 6) if 1.0 < number <= 1_000.0 else None


def _side(value: Any) -> str | None:
    text = (_clean(value) or "").casefold()
    if re.search(r"\bover\b", text):
        return "over"
    if re.search(r"\bunder\b", text):
        return "under"
    return None


def _line(*values: Any) -> float | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            number = float(value)
            if 0.0 <= number <= 500.0:
                return round(number, 6)
            continue
        text = _clean(value)
        if not text:
            continue
        match = _NUMBER_RE.search(text.replace("½", ".5"))
        if match:
            try:
                number = float(match.group(1))
            except ValueError:
                continue
            if 0.0 <= number <= 500.0:
                return round(number, 6)
    return None


def _stat(value: Any) -> str | None:
    text = " ".join((_clean(value) or "").casefold().replace("_", " ").replace("-", " ").split())
    if not text:
        return None
    if (
        "points rebounds assists" in text
        or "points + rebounds + assists" in text
        or re.search(r"\bpra\b", text)
    ):
        return "pra"
    if "rebound" in text:
        return "rebounds"
    if "assist" in text:
        return "assists"
    if "point" in text:
        return "points"
    return None


def _participant_name(value: Any) -> str | None:
    if isinstance(value, str):
        return _clean(value)
    if isinstance(value, dict):
        return _clean(
            value.get("name")
            or value.get("fullName")
            or value.get("participantName")
            or value.get("description")
        )
    return None


def _derived_player_name(market_name: str | None, stat: str | None) -> str | None:
    text = _clean(market_name)
    if not text or not stat:
        return None
    cleaned = re.sub(
        r"(?i)\b(player\s+)?(points\s*\+\s*rebounds\s*\+\s*assists|points\s+rebounds\s+assists|pra|points?|rebounds?|assists?)\b",
        " ",
        text,
    )
    cleaned = re.sub(r"(?i)\b(over\s*/?\s*under|o/u|total)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :-–—|/")
    if not cleaned or len(cleaned) > 100:
        return None
    # Generic market labels are not player identities.
    if cleaned.casefold() in {"player", "player props", "game", "match", "alternate"}:
        return None
    return cleaned


def _event_maps(document: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    candidates: list[Any] = []
    for source in (document, document.get("eventGroup") if isinstance(document.get("eventGroup"), dict) else {}):
        if isinstance(source, dict) and isinstance(source.get("events"), list):
            candidates.extend(source.get("events") or [])
    events: dict[str, dict[str, Any]] = {}
    team_names: set[str] = set()
    for row in candidates:
        if not isinstance(row, dict):
            continue
        event_id = _clean(row.get("id") or row.get("eventId"))
        if event_id:
            events[event_id] = row
        for participant in row.get("participants") or []:
            name = _participant_name(participant)
            if name:
                team_names.add(name.casefold())
    return events, team_names


def _best_player_name(
    *,
    selection: Mapping[str, Any],
    market: Mapping[str, Any],
    market_name: str | None,
    stat: str | None,
    team_names: set[str],
) -> str | None:
    direct = _clean(
        selection.get("playerName")
        or selection.get("player_name")
        or selection.get("participantName")
        or selection.get("description")
        or market.get("playerName")
        or market.get("player_name")
        or market.get("participantName")
    )
    if direct and direct.casefold() not in team_names and _side(direct) is None:
        return direct
    for container in (selection.get("participants"), market.get("participants")):
        if not isinstance(container, list):
            continue
        for participant in container:
            name = _participant_name(participant)
            if name and name.casefold() not in team_names and _side(name) is None:
                return name
    return _derived_player_name(market_name, stat)


def _canonical_offer(
    *,
    event_id: str | None,
    market_id: str | None,
    selection_id: str | None,
    market_name: str | None,
    selection: Mapping[str, Any],
    market: Mapping[str, Any],
    team_names: set[str],
    captured_at_utc: str,
) -> dict[str, Any] | None:
    stat = _stat(market_name)
    side = _side(selection.get("label") or selection.get("name") or selection.get("side"))
    line = _line(
        selection.get("points"),
        selection.get("line"),
        selection.get("displayLine"),
        selection.get("label"),
        market.get("line"),
    )
    player_name = _best_player_name(
        selection=selection,
        market=market,
        market_name=market_name,
        stat=stat,
        team_names=team_names,
    )
    display_odds = selection.get("displayOdds")
    american = _american_odds(
        selection.get("oddsAmerican")
        or selection.get("americanOdds")
        or display_odds
        or selection.get("odds")
    )
    decimal = _decimal_odds(
        selection.get("oddsDecimal")
        or selection.get("decimalOdds")
        or ((display_odds or {}).get("decimal") if isinstance(display_odds, dict) else None)
        or selection.get("trueOdds")
    )
    if not all((stat, side, line is not None, player_name)) or (american is None and decimal is None):
        return None
    offer: dict[str, Any] = {
        "sportsbook": "DraftKings",
        "player_name": player_name,
        "stat": stat,
        "side": side,
        "line": line,
        "market_captured_at_utc": captured_at_utc,
        "source_event_id": event_id,
        "source_market_id": market_id,
        "source_offer_id": selection_id,
    }
    if american is not None:
        offer["american_odds"] = american
    elif decimal is not None:
        offer["decimal_odds"] = decimal
    return offer


def _normalize_modern(document: Mapping[str, Any], captured_at_utc: str) -> list[dict[str, Any]]:
    events, team_names = _event_maps(document)
    markets_raw = document.get("markets")
    selections_raw = document.get("selections")
    if not isinstance(markets_raw, list) or not isinstance(selections_raw, list):
        return []
    markets: dict[str, dict[str, Any]] = {}
    for row in markets_raw:
        if not isinstance(row, dict):
            continue
        market_id = _clean(row.get("id") or row.get("marketId"))
        if market_id:
            markets[market_id] = row
    result: list[dict[str, Any]] = []
    for selection in selections_raw:
        if not isinstance(selection, dict):
            continue
        market_id = _clean(selection.get("marketId") or selection.get("market_id"))
        market = markets.get(market_id or "")
        if not market:
            continue
        event_id = _clean(market.get("eventId") or market.get("event_id"))
        market_type = market.get("marketType") if isinstance(market.get("marketType"), dict) else {}
        market_name = _clean(
            market.get("name")
            or market.get("label")
            or market_type.get("name")
            or market.get("marketName")
        )
        offer = _canonical_offer(
            event_id=event_id,
            market_id=market_id,
            selection_id=_clean(selection.get("id") or selection.get("selectionId") or selection.get("outcomeId")),
            market_name=market_name,
            selection=selection,
            market=market,
            team_names=team_names,
            captured_at_utc=captured_at_utc,
        )
        if offer:
            result.append(offer)
    return result


def _walk_market_objects(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        outcomes = value.get("outcomes")
        if isinstance(outcomes, list):
            found.append(value)
        for child in value.values():
            if isinstance(child, (dict, list)):
                found.extend(_walk_market_objects(child))
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                found.extend(_walk_market_objects(child))
    return found


def _normalize_legacy(document: Mapping[str, Any], captured_at_utc: str) -> list[dict[str, Any]]:
    _, team_names = _event_maps(document)
    result: list[dict[str, Any]] = []
    for market in _walk_market_objects(document.get("eventGroup") or document):
        market_name = _clean(
            market.get("label")
            or market.get("name")
            or market.get("marketName")
            or market.get("marketTypeName")
        )
        if _stat(market_name) is None:
            continue
        market_id = _clean(market.get("id") or market.get("marketId") or market.get("offerId"))
        event_id = _clean(market.get("eventId") or market.get("event_id"))
        for outcome in market.get("outcomes") or []:
            if not isinstance(outcome, dict):
                continue
            selection = dict(outcome)
            if selection.get("displayOdds") is None:
                selection["displayOdds"] = {
                    "american": outcome.get("oddsAmerican") or outcome.get("americanOdds"),
                    "decimal": outcome.get("oddsDecimal") or outcome.get("decimalOdds"),
                }
            offer = _canonical_offer(
                event_id=event_id,
                market_id=market_id,
                selection_id=_clean(outcome.get("id") or outcome.get("outcomeId") or outcome.get("selectionId")),
                market_name=market_name,
                selection=selection,
                market=market,
                team_names=team_names,
                captured_at_utc=captured_at_utc,
            )
            if offer:
                result.append(offer)
    return result


def normalize_draftkings_document(document: Any, *, captured_at_utc: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        raise WNBADraftKingsDirectModelInputError("DraftKings response must be a JSON object.")
    captured = captured_at_utc or _iso_now()
    offers = _normalize_modern(document, captured)
    if not offers:
        offers = _normalize_legacy(document, captured)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for offer in offers:
        identity = _hash(
            {
                "sportsbook": offer.get("sportsbook"),
                "player_name": offer.get("player_name"),
                "stat": offer.get("stat"),
                "side": offer.get("side"),
                "line": offer.get("line"),
                "source_event_id": offer.get("source_event_id"),
                "source_market_id": offer.get("source_market_id"),
                "source_offer_id": offer.get("source_offer_id"),
            }
        )
        if identity not in seen:
            deduped.append(offer)
            seen.add(identity)
    return deduped


def _response_json(response: Any, *, url: str) -> Any:
    status = getattr(response, "status_code", None)
    if status != 200:
        raise WNBADraftKingsDirectUpstreamError(
            f"DraftKings GET returned HTTP {status if status is not None else 'unknown'} for configured endpoint."
        )
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)) and len(content) > MAX_RESPONSE_BYTES:
        raise WNBADraftKingsDirectUpstreamError(
            f"DraftKings response exceeded {MAX_RESPONSE_BYTES} bytes."
        )
    try:
        return response.json()
    except Exception as exc:
        raise WNBADraftKingsDirectUpstreamError("DraftKings endpoint did not return valid JSON.") from exc


def _get(
    url: str,
    *,
    timeout_seconds: float,
    requester: Callable[..., Any] | None,
) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": "https://sportsbook.draftkings.com/leagues/basketball/wnba",
    }
    try:
        if requester is not None:
            try:
                return requester(url, headers=headers, timeout=timeout_seconds)
            except TypeError:
                return requester("GET", url, headers=headers, timeout=timeout_seconds)
        with httpx.Client(timeout=timeout_seconds, follow_redirects=False, headers=headers) as client:
            return client.get(url)
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        raise WNBADraftKingsDirectUpstreamError("DraftKings GET failed before a valid response was received.") from exc


def fetch_draftkings_canonical_feed(
    *,
    date: str,
    season: int,
    urls: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if not _DATE_RE.fullmatch(str(date)):
        raise WNBADraftKingsDirectModelInputError("Step 6D date must use YYYY-MM-DD.")
    try:
        season_int = int(season)
    except (TypeError, ValueError) as exc:
        raise WNBADraftKingsDirectModelInputError("Step 6D season must be an integer.") from exc
    environment = _environment(env)
    resolved_urls = resolve_draftkings_urls(urls, env=environment)
    timeout_seconds = _timeout(environment)
    captured = _iso_now()
    offers: list[dict[str, Any]] = []
    source_summaries: list[dict[str, Any]] = []
    for index, url in enumerate(resolved_urls):
        response = _get(url, timeout_seconds=timeout_seconds, requester=requester)
        document = _response_json(response, url=url)
        normalized = normalize_draftkings_document(document, captured_at_utc=captured)
        source_summaries.append(
            {
                "source_index": index,
                "host": (urlparse(url).hostname or "").casefold(),
                "normalized_offer_count": len(normalized),
                "http_status": 200,
            }
        )
        offers.extend(normalized)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for offer in offers:
        key = _hash(
            {
                "sportsbook": offer.get("sportsbook"),
                "player_name": offer.get("player_name"),
                "stat": offer.get("stat"),
                "side": offer.get("side"),
                "line": offer.get("line"),
                "source_event_id": offer.get("source_event_id"),
                "source_market_id": offer.get("source_market_id"),
                "source_offer_id": offer.get("source_offer_id"),
            }
        )
        if key not in seen:
            deduped.append(offer)
            seen.add(key)
    if not deduped:
        raise WNBADraftKingsDirectNotReadyError(
            "Configured DraftKings endpoints returned no supported WNBA points/rebounds/assists/PRA offers."
        )
    return {
        "schema_version": KYRE_FEED_SCHEMA_VERSION,
        "date": str(date),
        "season": season_int,
        "captured_at_utc": captured,
        "feed_source": "DraftKings public sportsbook JSON -> Kyre direct collector",
        "feed_format": CANONICAL_FEED_FORMAT,
        "odds_format": "american",
        "offers": deduped,
        "source_summary": source_summaries,
    }


def sync_draftkings_to_kyre_feed(
    *,
    date: str,
    season: int,
    urls: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    feed = fetch_draftkings_canonical_feed(
        date=date,
        season=season,
        urls=urls,
        env=env,
        requester=requester,
    )
    storage = write_kyre_market_feed(feed, path=path, env=env)
    identity = {
        "date": feed["date"],
        "season": feed["season"],
        "captured_at_utc": feed["captured_at_utc"],
        "offer_count": len(feed["offers"]),
        "content_sha256": storage["content_sha256"],
    }
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6d_draftkings_to_kyre_sync",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "provider_id": DRAFTKINGS_PROVIDER_ID,
        "synced": True,
        "offer_count": len(feed["offers"]),
        "source_summary": feed.get("source_summary") or [],
        "storage": storage,
        "sync_fingerprint_sha256": _hash(identity),
        "feed": feed,
        "safety": {
            "http_methods": ["GET"],
            "authentication_used": False,
            "cookies_used": False,
            "wager_action_performed": False,
            "paid_odds_vendor_used": False,
            "kyre_feed_written": True,
        },
    }


def collect_draftkings_direct_feed(
    *,
    date: str | None = None,
    season: int,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    target_date = date or datetime.now(timezone.utc).date().isoformat()
    sync = sync_draftkings_to_kyre_feed(
        date=target_date,
        season=season,
        env=env,
        requester=requester,
    )
    feed = sync["feed"]
    raw_feed = {"offers": feed["offers"]}
    fingerprint = _hash(
        {
            "provider_id": DRAFTKINGS_PROVIDER_ID,
            "date": feed["date"],
            "season": feed["season"],
            "captured_at_utc": feed["captured_at_utc"],
            "raw_feed_sha256": _hash(raw_feed),
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_feed_provider_collection",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "model_family": "direct_public_sportsbook_collection_to_kyre_owned_feed",
        "generated_at_utc": _iso_now(),
        "collection_id": f"wnba-6d-dk-{fingerprint[:20]}",
        "collection_fingerprint_sha256": fingerprint,
        "provider_id": DRAFTKINGS_PROVIDER_ID,
        "feed_source": feed["feed_source"],
        "feed_format": CANONICAL_FEED_FORMAT,
        "odds_format": "american",
        "date": feed["date"],
        "season": feed["season"],
        "collected_at_utc": feed["captured_at_utc"],
        "transport": {
            "method": "GET",
            "network_used": True,
            "configured_url_count": len(sync["source_summary"]),
            "authenticated": False,
        },
        "provider_configuration": {
            "provider_id": DRAFTKINGS_PROVIDER_ID,
            "kyre_owned_ingestion": True,
            "secret_required": False,
        },
        "raw_feed_sha256": _hash(raw_feed),
        "raw_feed": raw_feed,
        "kyre_feed_storage": sync["storage"],
        "collector_semantics": {
            "direct_sportsbook_get_only": True,
            "sportsbook_vendor_key_required": False,
            "paid_odds_aggregator_required": False,
            "kyre_persistent_feed_updated_before_step_5m": True,
            "market_data_cannot_modify_model_probability": True,
        },
    }
