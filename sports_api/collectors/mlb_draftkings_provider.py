"""MLB Step 11B — shadow-only DraftKings provider adapter.

The adapter converts explicitly configured public DraftKings JSON into the
frozen Step 11A provider-neutral core-market contract. It never guesses an
endpoint or game identity: callers must provide an exact DraftKings-event to
official MLB gamePk map. No team-name join, fuzzy match, synthetic ID, login,
cookie, browser automation, wager action, persistence write, or price
fabrication is allowed.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import (
    CONTRACT_STATUS as STEP11A_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP11A_MARKER,
    build_market_provider_game_snapshot,
    validate_market_provider_game_snapshot,
)

DATA_TYPE = "mlb_draftkings_provider_adapter_v1"
SCHEMA_VERSION = 1
STEP11B_BASE_MAIN_SHA = "733206c8fe8c0d219c5d76b8706eca652507de30"
ADAPTER_STATUS = "STEP11B_DRAFTKINGS_PROVIDER_ADAPTER_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP11B_DRAFTKINGS_PROVIDER_ADAPTER_GREEN"
PROVIDER_KEY = "draftkings"
PROVIDER_NAME = "DraftKings"
TRANSPORT = "anonymous_public_get_only_explicit_url"
DRAFTKINGS_URLS_ENV = "MLB_DRAFTKINGS_MARKET_URLS_JSON"
DRAFTKINGS_EVENT_GAMEPK_MAP_ENV = "MLB_DRAFTKINGS_EVENT_GAMEPK_MAP_JSON"
DRAFTKINGS_TIMEOUT_ENV = "MLB_DRAFTKINGS_REQUEST_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_URLS = 24
MAX_RESPONSE_BYTES = 15_000_000
DEFAULT_USER_AGENT = "kyre-sports-api/mlb-step11b (+market-research; GET-only)"

ALIASES = {
    "moneyline": {"moneyline", "money line", "game moneyline", "game money line"},
    "run_line": {"run line", "runline", "game run line", "spread", "game spread"},
    "total": {"total", "total runs", "game total", "game total runs"},
}
ROLES = {"away", "home", "over", "under"}
_AMERICAN = re.compile(r"^[+-]?\d+$")
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


class MLBDraftKingsProviderError(ValueError):
    pass


class MLBDraftKingsProviderNotReadyError(MLBDraftKingsProviderError):
    pass


class MLBDraftKingsProviderUpstreamError(RuntimeError):
    pass


def adapter_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step11b_base_main_sha": STEP11B_BASE_MAIN_SHA,
        "adapter_status": ADAPTER_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step11a_contract_status_required": STEP11A_STATUS,
        "step11a_final_certification_marker_required": STEP11A_MARKER,
        "step10_final_freeze_status_required": STEP10_STATUS,
        "step10_final_certification_marker_required": STEP10_MARKER,
        "provider_key": PROVIDER_KEY,
        "provider_name": PROVIDER_NAME,
        "public_get_only": True,
        "explicit_endpoint_configuration_required": True,
        "default_unverified_endpoint_allowed": False,
        "exact_provider_event_to_gamepk_map_required": True,
        "team_name_join_allowed": False,
        "player_name_join_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "price_fabrication_allowed": False,
        "fallback_price_fabrication_allowed": False,
        "login_or_account_session_allowed": False,
        "cookies_allowed": False,
        "browser_automation_allowed": False,
        "wager_actions_allowed": False,
        "shadow_adapter_only": True,
        "production_api_wiring_added_by_step11b": False,
        "production_runtime_wiring_added_by_step11b": False,
        "persistence_schema_changed_by_step11b": False,
        "production_database_writes_enabled": False,
        "provider_consensus_enabled_by_step11b": False,
        "provider_failover_enabled_by_step11b": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        **PROTECTED_INVARIANTS,
    }


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold()
    return (
        parsed.scheme.casefold() == "https"
        and (host == "draftkings.com" or host.endswith(".draftkings.com"))
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def resolve_draftkings_urls(urls: Sequence[str] | None = None, *, env: Mapping[str, str] | None = None) -> list[str]:
    environment = _env(env)
    if urls is None:
        raw = _clean(environment.get(DRAFTKINGS_URLS_ENV))
        if not raw:
            raise MLBDraftKingsProviderNotReadyError(f"{DRAFTKINGS_URLS_ENV} is not configured")
        try:
            urls = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MLBDraftKingsProviderError(f"{DRAFTKINGS_URLS_ENV} must be valid JSON") from exc
    if not isinstance(urls, Sequence) or isinstance(urls, (str, bytes)):
        raise MLBDraftKingsProviderError("DraftKings URLs must be a sequence")
    result: list[str] = []
    for value in urls:
        if not isinstance(value, str) or not value.strip():
            raise MLBDraftKingsProviderError("DraftKings URL entries must be non-empty strings")
        url = value.strip()
        if not _allowed_url(url):
            raise MLBDraftKingsProviderError("only HTTPS draftkings.com URLs without credentials/fragments are allowed")
        if url not in result:
            result.append(url)
    if not result:
        raise MLBDraftKingsProviderNotReadyError("no DraftKings URLs configured")
    if len(result) > MAX_URLS:
        raise MLBDraftKingsProviderError(f"at most {MAX_URLS} DraftKings URLs are allowed")
    return result


def resolve_event_gamepk_map(event_gamepk_map: Mapping[str, int] | None = None, *, env: Mapping[str, str] | None = None) -> dict[str, int]:
    environment = _env(env)
    if event_gamepk_map is None:
        raw = _clean(environment.get(DRAFTKINGS_EVENT_GAMEPK_MAP_ENV))
        if not raw:
            raise MLBDraftKingsProviderNotReadyError(f"{DRAFTKINGS_EVENT_GAMEPK_MAP_ENV} is not configured")
        try:
            event_gamepk_map = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MLBDraftKingsProviderError(f"{DRAFTKINGS_EVENT_GAMEPK_MAP_ENV} must be valid JSON") from exc
    if not isinstance(event_gamepk_map, Mapping):
        raise MLBDraftKingsProviderError("event_gamepk_map must be a mapping")
    result: dict[str, int] = {}
    for event_id, gamepk in event_gamepk_map.items():
        if not isinstance(event_id, str) or not event_id.strip():
            raise MLBDraftKingsProviderError("DraftKings event IDs must be non-empty strings")
        if isinstance(gamepk, bool) or not isinstance(gamepk, int) or gamepk <= 0:
            raise MLBDraftKingsProviderError("official MLB gamePk values must be positive integers")
        result[event_id.strip()] = gamepk
    if not result:
        raise MLBDraftKingsProviderNotReadyError("no exact DraftKings event/gamePk mappings configured")
    return result


def _timeout(environment: Mapping[str, str]) -> float:
    raw = _clean(environment.get(DRAFTKINGS_TIMEOUT_ENV))
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError as exc:
        raise MLBDraftKingsProviderError(f"{DRAFTKINGS_TIMEOUT_ENV} must be numeric") from exc
    if not math.isfinite(value) or not 0.5 <= value <= MAX_TIMEOUT_SECONDS:
        raise MLBDraftKingsProviderError("DraftKings timeout is outside supported bounds")
    return value


def describe_draftkings_provider(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _env(env)
    errors: list[str] = []
    try:
        urls = resolve_draftkings_urls(env=environment)
    except MLBDraftKingsProviderError as exc:
        urls = []
        errors.append(str(exc))
    try:
        mapping = resolve_event_gamepk_map(env=environment)
    except MLBDraftKingsProviderError as exc:
        mapping = {}
        errors.append(str(exc))
    try:
        timeout = _timeout(environment)
    except MLBDraftKingsProviderError as exc:
        timeout = DEFAULT_TIMEOUT_SECONDS
        errors.append(str(exc))
    return {
        "provider_key": PROVIDER_KEY,
        "provider_name": PROVIDER_NAME,
        "adapter_status": ADAPTER_STATUS,
        "ready": not errors,
        "configured_url_count": len(urls),
        "configured_event_gamepk_count": len(mapping),
        "request_timeout_seconds": timeout,
        "configuration_errors": errors,
        "secret_required": False,
        "authentication_used": False,
        "cookies_used": False,
        "http_method": "GET",
        "team_name_matching_used": False,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "price_fabrication_used": False,
        "production_runtime_wiring": False,
    }


def _utc(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MLBDraftKingsProviderError(f"{field} must be a timestamp string")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise MLBDraftKingsProviderError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MLBDraftKingsProviderError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _odds(value: Any, field: str) -> int:
    if isinstance(value, Mapping):
        return _odds(value.get("american") if value.get("american") is not None else value.get("americanOdds"), field)
    if isinstance(value, bool) or value is None:
        raise MLBDraftKingsProviderError(f"{field} has no American odds")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and _AMERICAN.fullmatch(value.strip()):
        result = int(value.strip())
    else:
        raise MLBDraftKingsProviderError(f"{field} has no American odds")
    if abs(result) < 100 or abs(result) > 100_000:
        raise MLBDraftKingsProviderError(f"{field} odds outside bounds")
    return result


def _line(value: Any, field: str) -> float:
    if isinstance(value, bool) or value is None:
        raise MLBDraftKingsProviderError(f"{field} has no line")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str) and _NUMBER.fullmatch(value.strip()):
        result = float(value.strip())
    else:
        raise MLBDraftKingsProviderError(f"{field} has no line")
    if not math.isfinite(result) or not -100 <= result <= 100:
        raise MLBDraftKingsProviderError(f"{field} line outside bounds")
    return result


def _market_type(market: Mapping[str, Any]) -> str | None:
    mt = market.get("marketType") if isinstance(market.get("marketType"), Mapping) else {}
    name = _clean(market.get("name") or market.get("label") or market.get("marketName") or market.get("marketTypeName") or mt.get("name"))
    if not name:
        return None
    normalized = " ".join(name.casefold().replace("_", " ").replace("-", " ").split())
    return next((key for key, aliases in ALIASES.items() if normalized in aliases), None)


def _role(selection: Mapping[str, Any]) -> str | None:
    for key in ("participantRole", "participant_role", "outcomeType", "outcome_type", "side", "role", "label", "name"):
        value = _clean(selection.get(key))
        if value and value.casefold() in ROLES:
            return value.casefold()
    return None


def _id(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None and not isinstance(value, bool) and str(value).strip():
            return str(value).strip()
    return None


def _event_id(row: Mapping[str, Any]) -> str | None:
    value = _id(row, "eventId", "event_id")
    if value:
        return value
    event = row.get("event")
    return _id(event, "id", "eventId") if isinstance(event, Mapping) else None


def _market_time(market: Mapping[str, Any]) -> str | None:
    value = _clean(market.get("marketTime") or market.get("startDate") or market.get("startDateTime") or market.get("startsAt"))
    return _utc(value, "market_time_utc") if value else None


def _eligible(market: Mapping[str, Any], phase: str) -> bool:
    status = _clean(market.get("status") or market.get("marketStatus"))
    if status and status.upper() not in {"OPEN", "ACTIVE"}:
        return False
    in_play = market.get("inPlay") if "inPlay" in market else market.get("in_play")
    if in_play is not None:
        if not isinstance(in_play, bool):
            raise MLBDraftKingsProviderError("inPlay must be boolean")
        if phase == "IN_PLAY" and not in_play:
            return False
        if phase == "PREGAME" and in_play:
            return False
    return True


def _selection_odds(selection: Mapping[str, Any], field: str) -> int:
    for value in (selection.get("oddsAmerican"), selection.get("americanOdds"), selection.get("displayOdds"), selection.get("odds")):
        if value is not None:
            try:
                return _odds(value, field)
            except MLBDraftKingsProviderError:
                pass
    raise MLBDraftKingsProviderError(f"{field} missing")


def _selection_line(selection: Mapping[str, Any], market: Mapping[str, Any], field: str) -> float:
    for value in (selection.get("points"), selection.get("line"), selection.get("handicap"), selection.get("spread"), market.get("line"), market.get("points")):
        if value is not None:
            try:
                return _line(value, field)
            except MLBDraftKingsProviderError:
                pass
    raise MLBDraftKingsProviderError(f"{field} missing")


def _one(selections: Sequence[Mapping[str, Any]], role: str, market_id: str) -> Mapping[str, Any]:
    rows = [row for row in selections if _role(row) == role]
    if len(rows) != 1:
        raise MLBDraftKingsProviderError(f"market {market_id} expected one {role} selection, found {len(rows)}")
    return rows[0]


def _normalize_market(market: Mapping[str, Any], selections: Sequence[Mapping[str, Any]], kind: str) -> dict[str, Any]:
    market_id = _id(market, "id", "marketId", "offerId")
    if not market_id:
        raise MLBDraftKingsProviderError("recognized core market has no market ID")
    result: dict[str, Any] = {"market_id": market_id, "market_time_utc": _market_time(market)}
    if kind in {"moneyline", "run_line"}:
        away, home = _one(selections, "away", market_id), _one(selections, "home", market_id)
        result.update({
            "away_odds": _selection_odds(away, f"{kind}.away_odds"),
            "home_odds": _selection_odds(home, f"{kind}.home_odds"),
            "away_selection_id": _id(away, "id", "selectionId", "outcomeId"),
            "home_selection_id": _id(home, "id", "selectionId", "outcomeId"),
        })
        if kind == "run_line":
            away_line = _selection_line(away, market, "run_line.away_line")
            home_line = _selection_line(home, market, "run_line.home_line")
            if not math.isclose(away_line, -home_line, abs_tol=1e-9):
                raise MLBDraftKingsProviderError("run-line sides must be exact opposites")
            result.update({"away_line": away_line, "home_line": home_line})
        return result
    over, under = _one(selections, "over", market_id), _one(selections, "under", market_id)
    over_line = _selection_line(over, market, "total.over_line")
    under_line = _selection_line(under, market, "total.under_line")
    if over_line < 0 or not math.isclose(over_line, under_line, abs_tol=1e-9):
        raise MLBDraftKingsProviderError("total sides must use the same nonnegative line")
    result.update({
        "line": over_line,
        "over_odds": _selection_odds(over, "total.over_odds"),
        "under_odds": _selection_odds(under, "total.under_odds"),
        "over_selection_id": _id(over, "id", "selectionId", "outcomeId"),
        "under_selection_id": _id(under, "id", "selectionId", "outcomeId"),
    })
    return result


def _walk(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        if isinstance(value.get("outcomes"), list):
            found.append(value)
        for child in value.values():
            if isinstance(child, (Mapping, list)):
                found.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (Mapping, list)):
                found.extend(_walk(child))
    return found


def _markets(document: Mapping[str, Any], event_id: str, phase: str) -> dict[str, dict[str, Any]]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    markets_raw, selections_raw = document.get("markets"), document.get("selections")
    if isinstance(markets_raw, list) and isinstance(selections_raw, list):
        selections: dict[str, list[Mapping[str, Any]]] = {}
        for row in selections_raw:
            if isinstance(row, Mapping):
                market_id = _id(row, "marketId", "market_id")
                if market_id:
                    selections.setdefault(market_id, []).append(row)
        for market in markets_raw:
            if not isinstance(market, Mapping) or _event_id(market) != event_id:
                continue
            kind = _market_type(market)
            if not kind or not _eligible(market, phase):
                continue
            market_id = _id(market, "id", "marketId", "offerId")
            normalized = _normalize_market(market, selections.get(market_id or "", []), kind)
            candidates.setdefault(kind, []).append(normalized)
    else:
        for market in _walk(document.get("eventGroup") or document):
            if _event_id(market) != event_id:
                continue
            kind = _market_type(market)
            if not kind or not _eligible(market, phase):
                continue
            outcomes = [row for row in market.get("outcomes", []) if isinstance(row, Mapping)]
            candidates.setdefault(kind, []).append(_normalize_market(market, outcomes, kind))
    result: dict[str, dict[str, Any]] = {}
    for kind, rows in candidates.items():
        rows.sort(key=lambda row: str(row["market_id"]))
        result[kind] = rows[0]
    return result


def _event_ids(document: Mapping[str, Any]) -> list[str]:
    result: set[str] = set()
    for container in (document, document.get("eventGroup") if isinstance(document.get("eventGroup"), Mapping) else {}):
        events = container.get("events") if isinstance(container, Mapping) else None
        if isinstance(events, list):
            for event in events:
                if isinstance(event, Mapping):
                    value = _id(event, "id", "eventId")
                    if value:
                        result.add(value)
    if isinstance(document.get("markets"), list):
        for market in document["markets"]:
            if isinstance(market, Mapping) and _event_id(market):
                result.add(_event_id(market))
    for market in _walk(document.get("eventGroup") or document):
        if _event_id(market):
            result.add(_event_id(market))
    return sorted(result)


def normalize_draftkings_game_document(
    document: Any,
    *,
    provider_event_id: str,
    official_game_id: int,
    event_gamepk_map: Mapping[str, int],
    market_phase: str,
    observed_at_utc: str,
    source_collected_at_utc: str | None = None,
) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise MLBDraftKingsProviderError("DraftKings response must be a JSON object")
    if not isinstance(provider_event_id, str) or not provider_event_id.strip():
        raise MLBDraftKingsProviderError("provider_event_id must be a non-empty string")
    if isinstance(official_game_id, bool) or not isinstance(official_game_id, int) or official_game_id <= 0:
        raise MLBDraftKingsProviderError("official_game_id must be a positive integer")
    if market_phase not in {"PREGAME", "IN_PLAY"}:
        raise MLBDraftKingsProviderError("market_phase must be PREGAME or IN_PLAY")
    event_id = provider_event_id.strip()
    mapping = resolve_event_gamepk_map(event_gamepk_map)
    if mapping.get(event_id) != official_game_id:
        raise MLBDraftKingsProviderError("exact DraftKings event to official MLB gamePk mapping mismatch")
    observed = _utc(observed_at_utc, "observed_at_utc")
    collected = _utc(source_collected_at_utc or observed, "source_collected_at_utc")
    if collected > observed:
        raise MLBDraftKingsProviderError("source_collected_at_utc cannot be after observed_at_utc")
    markets = _markets(document, event_id, market_phase)
    if not markets:
        raise MLBDraftKingsProviderNotReadyError("no usable exact DraftKings core markets for mapped event")
    snapshot = build_market_provider_game_snapshot(
        provider_key=PROVIDER_KEY,
        provider_name=PROVIDER_NAME,
        provider_event_id=event_id,
        official_game_id=official_game_id,
        observed_at_utc=observed,
        source_collected_at_utc=collected,
        market_phase=market_phase,
        transport=TRANSPORT,
        source_payload_sha256=_hash(document),
        markets=markets,
        source_complete=True,
        exact_official_game_id_verified=True,
        fuzzy_matching_used=False,
        synthetic_game_id_used=False,
        price_fabrication_used=False,
        step10_final_freeze_status=STEP10_STATUS,
        step10_final_certification_marker=STEP10_MARKER,
    )
    validation = validate_market_provider_game_snapshot(snapshot)
    if validation.get("snapshot_valid") is not True:
        raise MLBDraftKingsProviderError(f"Step 11A validation failed: {validation.get('failures')}")
    return snapshot


def _response_json(response: Any) -> Mapping[str, Any]:
    status = getattr(response, "status_code", None)
    if status != 200:
        raise MLBDraftKingsProviderUpstreamError(f"DraftKings GET returned HTTP {status}")
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)) and len(content) > MAX_RESPONSE_BYTES:
        raise MLBDraftKingsProviderUpstreamError("DraftKings response exceeded size bound")
    try:
        value = response.json()
    except Exception as exc:
        raise MLBDraftKingsProviderUpstreamError("DraftKings response was not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise MLBDraftKingsProviderUpstreamError("DraftKings response JSON must be an object")
    return value


def _get(url: str, *, timeout: float, requester: Callable[..., Any] | None) -> Any:
    headers = {"Accept": "application/json", "User-Agent": DEFAULT_USER_AGENT, "Referer": "https://sportsbook.draftkings.com/leagues/baseball/mlb"}
    try:
        if requester is not None:
            try:
                return requester(url, headers=headers, timeout=timeout)
            except TypeError:
                return requester("GET", url, headers=headers, timeout=timeout)
        with httpx.Client(timeout=timeout, follow_redirects=False, headers=headers) as client:
            return client.get(url)
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        raise MLBDraftKingsProviderUpstreamError("DraftKings GET failed") from exc


def collect_draftkings_provider_snapshots(
    *,
    market_phase: str,
    urls: Sequence[str] | None = None,
    event_gamepk_map: Mapping[str, int] | None = None,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    if market_phase not in {"PREGAME", "IN_PLAY"}:
        raise MLBDraftKingsProviderError("market_phase must be PREGAME or IN_PLAY")
    environment = _env(env)
    resolved_urls = resolve_draftkings_urls(urls, env=environment)
    mapping = resolve_event_gamepk_map(event_gamepk_map, env=environment)
    timeout = _timeout(environment)
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise MLBDraftKingsProviderError("now_utc must be timezone-aware")
    observed = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    snapshots: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, url in enumerate(resolved_urls):
        document = _response_json(_get(url, timeout=timeout, requester=requester))
        event_ids = _event_ids(document)
        mapped = [event_id for event_id in event_ids if event_id in mapping]
        summaries.append({"source_index": index, "url_sha256": hashlib.sha256(url.encode()).hexdigest(), "payload_sha256": _hash(document), "candidate_event_count": len(event_ids), "mapped_event_count": len(mapped)})
        for event_id in mapped:
            try:
                snapshot = normalize_draftkings_game_document(document, provider_event_id=event_id, official_game_id=mapping[event_id], event_gamepk_map=mapping, market_phase=market_phase, observed_at_utc=observed)
            except MLBDraftKingsProviderError as exc:
                rejected.append({"provider_event_id": event_id, "official_game_id": mapping[event_id], "reason": f"{type(exc).__name__}: {exc}"})
                continue
            key = str(snapshot["record_key"])
            if key not in seen:
                snapshots.append(snapshot)
                seen.add(key)
    snapshots.sort(key=lambda row: (int(row["official_game_id"]), str(row["provider_event_id"])))
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "provider_key": PROVIDER_KEY,
        "provider_name": PROVIDER_NAME,
        "adapter_status": ADAPTER_STATUS,
        "market_phase": market_phase,
        "collected_at_utc": observed,
        "transport": TRANSPORT,
        "http_methods": ["GET"],
        "configured_url_count": len(resolved_urls),
        "configured_event_gamepk_count": len(mapping),
        "source_count": len(summaries),
        "snapshot_count": len(snapshots),
        "rejected_snapshot_count": len(rejected),
        "team_name_matching_used": False,
        "player_name_matching_used": False,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "price_fabrication_used": False,
        "production_runtime_wiring": False,
        "production_database_writes": False,
        "source_summaries": summaries,
        "snapshots": snapshots,
        "rejected_snapshots": rejected,
    }


__all__ = [
    "DATA_TYPE", "SCHEMA_VERSION", "STEP11B_BASE_MAIN_SHA", "ADAPTER_STATUS",
    "FINAL_CERTIFICATION_MARKER", "PROVIDER_KEY", "PROVIDER_NAME", "TRANSPORT",
    "DRAFTKINGS_URLS_ENV", "DRAFTKINGS_EVENT_GAMEPK_MAP_ENV", "DRAFTKINGS_TIMEOUT_ENV",
    "MLBDraftKingsProviderError", "MLBDraftKingsProviderNotReadyError",
    "MLBDraftKingsProviderUpstreamError", "adapter_manifest", "resolve_draftkings_urls",
    "resolve_event_gamepk_map", "describe_draftkings_provider",
    "normalize_draftkings_game_document", "collect_draftkings_provider_snapshots",
]
