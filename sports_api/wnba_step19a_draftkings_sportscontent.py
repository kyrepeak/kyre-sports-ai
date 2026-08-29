"""WNBA Step 19A: current DraftKings sportscontent transport adapter.

Step 18 intentionally left sportsbook retrieval behind the hosted Kyre API.
The older Step-6D DraftKings transport used an unofficial v5 endpoint that can
now return HTTP 403 on hosted runners. Step 19A is an additive, default-OFF
transport shim that preserves the frozen canonical normalizer and Step-6I
reconciliation/write guard while replacing only the upstream public GET path.

Safety:
- no API key, sportsbook login, account, cookie jar, or wager action;
- GET-only requests to a fixed DraftKings HTTPS host;
- current WNBA category/subcategory IDs are discovered from league metadata;
- only pregame Points/Rebounds/Assists/PRA O/U markets are accepted;
- Step 6I still reconciles the exact snapshot against official WNBA evidence
  before any durable market-feed write can occur.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any

from curl_cffi import requests as cffi_requests

from sports_api.collectors import wnba_draftkings_direct as _frozen_dk
from sports_api.wnba_official_reconciliation import extract_draftkings_events
import sports_api.wnba_reconciled_direct_sync as _step6i
import sports_api.wnba_step6d_direct_integration as _step6d

MODEL_SOURCE = "Kyre Sports API WNBA Step 19A DraftKings sportscontent transport"
MODEL_VERSION = "wnba_step_19a_draftkings_sportscontent_v1"
SCHEMA_VERSION = MODEL_VERSION
STEP19A_ENABLED_ENV = "WNBA_STEP19A_DRAFTKINGS_SPORTSCONTENT_ENABLED"
STEP19A_SITE_ENV = "WNBA_STEP19A_DRAFTKINGS_SITE"
WNBA_LEAGUE_ID = 94682
SPORTSCONTENT_HOST = "sportsbook-nash.draftkings.com"
DEFAULT_SITE = "dkusaz"
ALLOWED_SITES = ("dkusaz", "dkusnj", "dkusil")
MAX_RESPONSE_BYTES = 15_000_000
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_TARGET_MARKETS: dict[tuple[str, str], str] = {
    ("Player Points", "Points O/U"): "points",
    ("Player Rebounds", "Rebounds O/U"): "rebounds",
    ("Player Assists", "Assists O/U"): "assists",
    ("Player Combos", "Pts + Reb + Ast O/U"): "pra",
}
_REQUIRED_STATS = frozenset(_TARGET_MARKETS.values())

_ORIGINAL_DESCRIBE = _step6d.describe_draftkings_direct_onboarding
_ORIGINAL_FETCH_VERIFIED = _step6i.fetch_verified_draftkings_snapshot


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def step19a_sportscontent_enabled(env: Mapping[str, str] | None = None) -> bool:
    return _truthy(_environment(env).get(STEP19A_ENABLED_ENV))


def _site_order(env: Mapping[str, str]) -> tuple[str, ...]:
    preferred = str(env.get(STEP19A_SITE_ENV) or DEFAULT_SITE).strip().casefold()
    if preferred not in ALLOWED_SITES:
        raise _frozen_dk.WNBADraftKingsDirectModelInputError(
            f"{STEP19A_SITE_ENV} must be one of {', '.join(ALLOWED_SITES)}."
        )
    return (preferred,) + tuple(site for site in ALLOWED_SITES if site != preferred)


def _league_url(site: str) -> str:
    return f"https://{SPORTSCONTENT_HOST}/api/sportscontent/{site}/v1/leagues/{WNBA_LEAGUE_ID}"


def _subcategory_url(site: str, category_id: str, subcategory_id: str) -> str:
    return (
        f"https://{SPORTSCONTENT_HOST}/api/sportscontent/{site}/v1/leagues/{WNBA_LEAGUE_ID}"
        f"/categories/{category_id}/subcategories/{subcategory_id}"
    )


def _response_json(response: Any) -> dict[str, Any]:
    status = getattr(response, "status_code", None)
    if status != 200:
        raise _frozen_dk.WNBADraftKingsDirectUpstreamError(
            f"DraftKings sportscontent GET returned HTTP {status if status is not None else 'unknown'}."
        )
    content = getattr(response, "content", b"")
    if isinstance(content, (bytes, bytearray)) and len(content) > MAX_RESPONSE_BYTES:
        raise _frozen_dk.WNBADraftKingsDirectUpstreamError("DraftKings sportscontent response exceeded the size limit.")
    try:
        body = response.json()
    except Exception as exc:
        raise _frozen_dk.WNBADraftKingsDirectUpstreamError(
            "DraftKings sportscontent endpoint did not return valid JSON."
        ) from exc
    if not isinstance(body, dict):
        raise _frozen_dk.WNBADraftKingsDirectUpstreamError("DraftKings sportscontent response must be a JSON object.")
    return body


def _get_json(
    url: str,
    *,
    timeout_seconds: float,
    requester: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://sportsbook.draftkings.com/leagues/basketball/wnba",
        "User-Agent": "Mozilla/5.0 (compatible; kyre-sports-api/wnba-step19a; GET-only)",
    }
    try:
        if requester is not None:
            response = requester(url, headers=headers, timeout=timeout_seconds)
        else:
            response = cffi_requests.get(
                url,
                headers=headers,
                impersonate="chrome120",
                timeout=timeout_seconds,
                allow_redirects=True,
            )
    except Exception as exc:
        raise _frozen_dk.WNBADraftKingsDirectUpstreamError(
            "DraftKings sportscontent GET failed before a valid response was received."
        ) from exc
    return _response_json(response)


def _discover_pregame_targets(
    *,
    env: Mapping[str, str],
    requester: Callable[..., Any] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    timeout_seconds = _frozen_dk._timeout(env)
    failures: list[str] = []
    for site in _site_order(env):
        try:
            league = _get_json(_league_url(site), timeout_seconds=timeout_seconds, requester=requester)
        except _frozen_dk.WNBADraftKingsDirectUpstreamError as exc:
            failures.append(f"{site}:{type(exc).__name__}")
            continue
        categories = [row for row in (league.get("categories") or []) if isinstance(row, dict)]
        subcategories = [row for row in (league.get("subcategories") or []) if isinstance(row, dict)]
        category_names = {str(row.get("id")): str(row.get("name") or "") for row in categories}
        discovered: dict[str, dict[str, str]] = {}
        for row in subcategories:
            category_id = str(row.get("categoryId") or "").strip()
            subcategory_id = str(row.get("id") or "").strip()
            category_name = category_names.get(category_id, "")
            subcategory_name = str(row.get("name") or "").strip()
            stat = _TARGET_MARKETS.get((category_name, subcategory_name))
            if stat and category_id and subcategory_id:
                discovered[stat] = {
                    "stat": stat,
                    "category_id": category_id,
                    "category_name": category_name,
                    "subcategory_id": subcategory_id,
                    "subcategory_name": subcategory_name,
                }
        if frozenset(discovered) == _REQUIRED_STATS:
            return site, [discovered[stat] for stat in ("points", "rebounds", "assists", "pra")]
        failures.append(f"{site}:required_markets_missing")
    raise _frozen_dk.WNBADraftKingsDirectNotReadyError(
        "Step 19A could not discover all current WNBA Points/Rebounds/Assists/PRA pregame O/U markets: "
        + ", ".join(failures)
    )


def describe_step19a_draftkings_onboarding(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _environment(env)
    if not step19a_sportscontent_enabled(environment):
        return _ORIGINAL_DESCRIBE(environment)
    try:
        sites = _site_order(environment)
        configuration_error = None
        ready = True
    except _frozen_dk.WNBADraftKingsDirectModelInputError as exc:
        sites = ()
        configuration_error = str(exc)
        ready = False
    return {
        "provider_id": _frozen_dk.DRAFTKINGS_PROVIDER_ID,
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "ready": ready,
        "configured_url_count": 4 if ready else 0,
        "request_timeout_seconds": _frozen_dk._timeout(environment),
        "configuration_error": configuration_error,
        "secret_required": False,
        "authentication_used": False,
        "cookies_used": False,
        "http_method": "GET",
        "allowed_host_suffix": "draftkings.com",
        "sportscontent_host": SPORTSCONTENT_HOST,
        "wnba_league_id": WNBA_LEAGUE_ID,
        "site_preference_order": list(sites),
        "dynamic_market_discovery": True,
        "target_stats": ["points", "rebounds", "assists", "pra"],
        "semantics": {
            "public_endpoint_only": True,
            "provider_api_key_required": False,
            "browser_tls_transport": True,
            "pregame_ou_only": True,
            "no_wager_actions": True,
            "no_login_or_account_session": True,
            "unofficial_endpoint_may_change": True,
            "step_6i_reconciliation_still_required_before_write": True,
        },
    }


def _offer_identity(offer: Mapping[str, Any]) -> str:
    source_offer_id = str(offer.get("source_offer_id") or "").strip()
    if source_offer_id:
        return source_offer_id
    raw = json.dumps(dict(offer), sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def build_step19a_draftkings_snapshot(
    *,
    date: str,
    season: int,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    environment = _environment(env)
    if not step19a_sportscontent_enabled(environment):
        raise _frozen_dk.WNBADraftKingsDirectNotReadyError(f"{STEP19A_ENABLED_ENV}=true is required.")
    if not _DATE_RE.fullmatch(str(date)):
        raise _frozen_dk.WNBADraftKingsDirectModelInputError("Step 19A date must use YYYY-MM-DD.")
    try:
        season_int = int(season)
        datetime.strptime(str(date), "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise _frozen_dk.WNBADraftKingsDirectModelInputError("Step 19A date/season is invalid.") from exc

    timeout_seconds = _frozen_dk._timeout(environment)
    site, targets = _discover_pregame_targets(env=environment, requester=requester)
    captured = datetime.now(timezone.utc).isoformat()
    offers: list[dict[str, Any]] = []
    events_by_id: dict[str, dict[str, Any]] = {}
    source_summary: list[dict[str, Any]] = []

    for target in targets:
        document = _get_json(
            _subcategory_url(site, target["category_id"], target["subcategory_id"]),
            timeout_seconds=timeout_seconds,
            requester=requester,
        )
        normalized = [
            row
            for row in _frozen_dk.normalize_draftkings_document(document, captured_at_utc=captured)
            if row.get("stat") == target["stat"]
        ]
        for event in extract_draftkings_events(document):
            event_id = str(event.get("source_event_id") or "").strip()
            if not event_id:
                continue
            existing = events_by_id.get(event_id)
            if existing is None or len(event.get("participant_keys") or []) > len(existing.get("participant_keys") or []):
                events_by_id[event_id] = event
        offers.extend(normalized)
        source_summary.append(
            {
                "site": site,
                "category_id": target["category_id"],
                "subcategory_id": target["subcategory_id"],
                "stat": target["stat"],
                "http_status": 200,
                "normalized_offer_count": len(normalized),
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for offer in offers:
        identity = _offer_identity(offer)
        if identity not in seen:
            deduped.append(offer)
            seen.add(identity)

    stat_counts = {stat: sum(1 for row in deduped if row.get("stat") == stat) for stat in _REQUIRED_STATS}
    side_counts = {
        stat: {
            "over": sum(1 for row in deduped if row.get("stat") == stat and row.get("side") == "over"),
            "under": sum(1 for row in deduped if row.get("stat") == stat and row.get("side") == "under"),
        }
        for stat in _REQUIRED_STATS
    }
    blockers = [stat for stat in sorted(_REQUIRED_STATS) if stat_counts.get(stat, 0) <= 0]
    blockers.extend(
        f"{stat}_missing_two_sided_market"
        for stat in sorted(_REQUIRED_STATS)
        if side_counts[stat]["over"] <= 0 or side_counts[stat]["under"] <= 0
    )
    if blockers:
        raise _frozen_dk.WNBADraftKingsDirectNotReadyError(
            "Step 19A current DraftKings feed is incomplete: " + ", ".join(blockers)
        )
    if not events_by_id:
        raise _frozen_dk.WNBADraftKingsDirectNotReadyError("Step 19A current DraftKings feed returned no event metadata.")

    return {
        "schema_version": "wnba_step_6c_owned_market_feed_v1",
        "date": str(date),
        "season": season_int,
        "captured_at_utc": captured,
        "feed_source": "DraftKings current sportscontent public GET -> Kyre Step 19A transport",
        "feed_format": "canonical_offers_v1",
        "odds_format": "american",
        "offers": deduped,
        "source_events": sorted(events_by_id.values(), key=lambda row: str(row.get("source_event_id") or "")),
        "source_summary": source_summary,
        "step19a": {
            "model_version": MODEL_VERSION,
            "sportscontent_site": site,
            "wnba_league_id": WNBA_LEAGUE_ID,
            "stat_counts": stat_counts,
            "side_counts": side_counts,
            "provider_api_key_used": False,
        },
    }


def fetch_verified_draftkings_snapshot_step19a(*, date: str, season: int, env=None) -> dict[str, Any]:
    environment = _environment(env)
    if not step19a_sportscontent_enabled(environment):
        return _ORIGINAL_FETCH_VERIFIED(date=date, season=season, env=environment)
    return build_step19a_draftkings_snapshot(date=date, season=season, env=environment)


def install_step19a_sportscontent_transport() -> dict[str, Any]:
    """Patch only runtime seams already owned by Step 6D/6I; frozen files stay unchanged."""
    _step6d.describe_draftkings_direct_onboarding = describe_step19a_draftkings_onboarding
    _step6i.fetch_verified_draftkings_snapshot = fetch_verified_draftkings_snapshot_step19a
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "patched_step6d_status_transport": True,
        "patched_step6i_verified_snapshot_transport": True,
        "frozen_step6d_source_modified": False,
        "frozen_step6i_source_modified": False,
        "provider_api_key_required": False,
        "wager_action_supported": False,
    }


INSTALLATION = install_step19a_sportscontent_transport()

__all__ = [
    "ALLOWED_SITES",
    "INSTALLATION",
    "MODEL_VERSION",
    "STEP19A_ENABLED_ENV",
    "STEP19A_SITE_ENV",
    "WNBA_LEAGUE_ID",
    "build_step19a_draftkings_snapshot",
    "describe_step19a_draftkings_onboarding",
    "fetch_verified_draftkings_snapshot_step19a",
    "install_step19a_sportscontent_transport",
    "step19a_sportscontent_enabled",
]
