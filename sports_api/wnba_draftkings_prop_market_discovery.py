"""WNBA Step 6F: resolve and live-validate DraftKings player-prop endpoints.

Step 6E verified the current WNBA league family (league id 94682) but did not
find a player-prop endpoint that Step 6D could consume. Step 6F narrows the
search to the four model markets we actually need: points, rebounds, assists,
and PRA.

The implementation is intentionally fail-closed:
- GET only; no login, cookies, account session, browser automation, or wagers.
- bounded, explicitly enumerated DraftKings endpoint families only.
- candidate category/subcategory IDs are treated as untrusted hints until a
  live response returns WNBA data and real two-sided player-prop offers.
- no candidate is written into Step 6D configuration automatically.
- no scheduler/model/Monte-Carlo activation occurs here.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from sports_api.collectors.wnba_draftkings_direct import (
    DEFAULT_USER_AGENT,
    MAX_RESPONSE_BYTES,
    normalize_draftkings_document,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6F DraftKings prop-market discovery"
MODEL_VERSION = "wnba_step_6f_draftkings_prop_market_discovery_v1"
SCHEMA_VERSION = MODEL_VERSION

WNBA_LEAGUE_ID = "94682"
REQUIRED_STATS = ("points", "rebounds", "assists", "pra")

TIMEOUT_ENV = "WNBA_DRAFTKINGS_PROP_DISCOVERY_TIMEOUT_SECONDS"
CANDIDATES_ENV = "WNBA_DRAFTKINGS_PROP_DISCOVERY_CANDIDATES_JSON"
DEFAULT_TIMEOUT_SECONDS = 12.0
MAX_TIMEOUT_SECONDS = 30.0
MAX_CANDIDATES = 16

CONTROLLED_DATA_BASE = (
    "https://sportsbook-nash.draftkings.com/sites/US-SB/api/sportscontent/"
    "controldata/league/leagueSubcategory/v1/markets"
)

# Public 2026 references disagree across endpoint generations. That is exactly
# why these are candidates, not configuration. The controlled-data family was
# observed with shared basketball subcategory ids; the dkusva family is kept as
# an independent WNBA-specific fallback. Every candidate must pass a live probe.
CONTROLLED_DATA_SUBCATEGORY_HINTS = {
    "points": "16477",
    "assists": "16478",
    "rebounds": "16479",
    "pra": "16483",
}

DKUSVA_CATEGORY_SUBCATEGORY_HINTS = {
    "points": ("1215", "12488"),
    "rebounds": ("1216", "12492"),
    "assists": ("1217", "12495"),
    "pra": ("583", "5001"),
}


class WNBADraftKingsPropDiscoveryInputError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold()
    return (
        parsed.scheme.casefold() == "https"
        and bool(host)
        and (host == "draftkings.com" or host.endswith(".draftkings.com"))
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def _timeout(env: Mapping[str, str]) -> float:
    raw = _clean(env.get(TIMEOUT_ENV))
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError as exc:
        raise WNBADraftKingsPropDiscoveryInputError(f"{TIMEOUT_ENV} must be numeric.") from exc
    if not 0.5 <= value <= MAX_TIMEOUT_SECONDS:
        raise WNBADraftKingsPropDiscoveryInputError(
            f"{TIMEOUT_ENV} must be between 0.5 and {MAX_TIMEOUT_SECONDS} seconds."
        )
    return value


def build_controlled_data_url(stat: str, subcategory_id: str) -> str:
    stat_key = str(stat).strip().casefold()
    if stat_key not in REQUIRED_STATS:
        raise WNBADraftKingsPropDiscoveryInputError(f"Unsupported Step 6F stat: {stat!r}.")
    sid = str(subcategory_id).strip()
    if not sid.isdigit():
        raise WNBADraftKingsPropDiscoveryInputError("DraftKings subcategory ids must be numeric strings.")
    params = {
        "isBatchable": "false",
        "templateVars": f"{WNBA_LEAGUE_ID},{sid}",
        "eventsQuery": (
            f"$filter=leagueId eq '{WNBA_LEAGUE_ID}' "
            f"AND clientMetadata/Subcategories/any(s: s/Id eq '{sid}')"
        ),
        "marketsQuery": f"$filter=clientMetadata/subCategoryId eq '{sid}'",
        "include": "Events",
        "entity": "events",
    }
    return CONTROLLED_DATA_BASE + "?" + urlencode(params)


def default_prop_candidates() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for stat in REQUIRED_STATS:
        sid = CONTROLLED_DATA_SUBCATEGORY_HINTS[stat]
        rows.append(
            {
                "candidate_id": f"controlled_{stat}_{sid}",
                "family": "controlled_data_league_subcategory",
                "expected_stat": stat,
                "category_id": "",
                "subcategory_id": sid,
                "url": build_controlled_data_url(stat, sid),
            }
        )
    for stat in REQUIRED_STATS:
        category_id, subcategory_id = DKUSVA_CATEGORY_SUBCATEGORY_HINTS[stat]
        rows.append(
            {
                "candidate_id": f"dkusva_{stat}_{category_id}_{subcategory_id}",
                "family": "dkusva_category_subcategory",
                "expected_stat": stat,
                "category_id": category_id,
                "subcategory_id": subcategory_id,
                "url": (
                    "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusva/v1/"
                    f"leagues/{WNBA_LEAGUE_ID}/categories/{category_id}/subcategories/{subcategory_id}"
                ),
            }
        )
    return rows


def resolve_prop_candidates(
    candidates: Sequence[Mapping[str, Any]] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    environment = _environment(env)
    if candidates is None:
        raw = _clean(environment.get(CANDIDATES_ENV))
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise WNBADraftKingsPropDiscoveryInputError(f"{CANDIDATES_ENV} must be valid JSON.") from exc
            if not isinstance(parsed, list):
                raise WNBADraftKingsPropDiscoveryInputError(f"{CANDIDATES_ENV} must be a JSON array.")
            candidates = parsed
        else:
            candidates = default_prop_candidates()

    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise WNBADraftKingsPropDiscoveryInputError("Step 6F candidates must be a sequence.")
    if not candidates or len(candidates) > MAX_CANDIDATES:
        raise WNBADraftKingsPropDiscoveryInputError(f"Step 6F requires 1 through {MAX_CANDIDATES} candidates.")

    result: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for index, row in enumerate(candidates):
        if not isinstance(row, Mapping):
            raise WNBADraftKingsPropDiscoveryInputError("Every Step 6F candidate must be an object.")
        stat = (_clean(row.get("expected_stat")) or "").casefold()
        if stat not in REQUIRED_STATS:
            raise WNBADraftKingsPropDiscoveryInputError("Every candidate needs a supported expected_stat.")
        candidate_id = _clean(row.get("candidate_id")) or f"candidate_{index + 1}"
        family = _clean(row.get("family")) or "custom"
        category_id = _clean(row.get("category_id")) or ""
        subcategory_id = _clean(row.get("subcategory_id")) or ""
        url = _clean(row.get("url"))
        if not url or not _allowed_url(url):
            raise WNBADraftKingsPropDiscoveryInputError("Step 6F accepts HTTPS draftkings.com URLs only.")
        if candidate_id in seen_ids:
            raise WNBADraftKingsPropDiscoveryInputError("Step 6F candidate ids must be unique.")
        if url in seen_urls:
            continue
        result.append(
            {
                "candidate_id": candidate_id,
                "family": family,
                "expected_stat": stat,
                "category_id": category_id,
                "subcategory_id": subcategory_id,
                "url": url,
            }
        )
        seen_ids.add(candidate_id)
        seen_urls.add(url)
    return result


def get_prop_market_discovery_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _environment(env)
    try:
        candidates = resolve_prop_candidates(env=environment)
        timeout = _timeout(environment)
        blocker = None
    except WNBADraftKingsPropDiscoveryInputError as exc:
        candidates = []
        timeout = DEFAULT_TIMEOUT_SECONDS
        blocker = str(exc)
    counts = {stat: 0 for stat in REQUIRED_STATS}
    for row in candidates:
        counts[row["expected_stat"]] += 1
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6f_draftkings_prop_market_discovery_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "wnba_league_id": WNBA_LEAGUE_ID,
        "required_stats": list(REQUIRED_STATS),
        "candidate_count": len(candidates),
        "candidate_counts_by_stat": counts,
        "candidates": candidates,
        "request_timeout_seconds": timeout,
        "configuration_ready": blocker is None and all(counts.values()),
        "configuration_blocker": blocker,
        "live_probe_performed": False,
        "all_required_stats_verified": False,
        "step6d_configuration_generated": False,
        "safety": {
            "http_method": "GET",
            "authentication_used": False,
            "cookies_used": False,
            "sportsbook_account_required": False,
            "wager_actions": False,
            "paid_odds_vendor_used": False,
            "scheduler_enabled": False,
            "monte_carlo_run": False,
        },
    }


def _response_json(response: Any) -> tuple[int | None, Any | None, str | None]:
    status = getattr(response, "status_code", None)
    if status != 200:
        return status, None, f"http_{status if status is not None else 'unknown'}"
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)) and len(content) > MAX_RESPONSE_BYTES:
        return status, None, "response_too_large"
    try:
        document = response.json()
    except Exception:
        return status, None, "invalid_json"
    if not isinstance(document, dict):
        return status, None, "json_not_object"
    return status, document, None


def _document_wnba_identity(document: Any) -> bool:
    if not isinstance(document, dict):
        return False
    encoded = json.dumps(document, ensure_ascii=False, default=str).casefold()
    return '"94682"' in encoded or ':94682' in encoded or "wnba" in encoded


def _document_shape(document: Any) -> dict[str, int | bool]:
    if not isinstance(document, dict):
        return {"json_object": False, "event_count": 0, "market_count": 0, "selection_count": 0}
    event_group = document.get("eventGroup") if isinstance(document.get("eventGroup"), dict) else {}
    events = document.get("events") if isinstance(document.get("events"), list) else event_group.get("events")
    markets = document.get("markets") if isinstance(document.get("markets"), list) else []
    selections = document.get("selections") if isinstance(document.get("selections"), list) else []
    return {
        "json_object": True,
        "event_count": len(events) if isinstance(events, list) else 0,
        "market_count": len(markets),
        "selection_count": len(selections),
    }


def _compatibility_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt current public selection aliases without modifying frozen Step 6D."""
    adapted = deepcopy(dict(document))
    selections = adapted.get("selections")
    if isinstance(selections, list):
        for row in selections:
            if not isinstance(row, dict):
                continue
            if row.get("side") is None and row.get("outcomeType") is not None:
                row["side"] = row.get("outcomeType")
            if row.get("line") is None and row.get("points") is None and row.get("handicap") is not None:
                row["line"] = row.get("handicap")
            if row.get("line") is None and row.get("points") is None and row.get("milestoneValue") is not None:
                try:
                    row["line"] = float(row["milestoneValue"]) - 0.5
                except (TypeError, ValueError):
                    pass
    return adapted


def normalize_prop_candidate_document(
    document: Mapping[str, Any],
    *,
    expected_stat: str,
    captured_at_utc: str | None = None,
) -> list[dict[str, Any]]:
    stat = str(expected_stat).strip().casefold()
    if stat not in REQUIRED_STATS:
        raise WNBADraftKingsPropDiscoveryInputError("Unsupported expected_stat for normalization.")
    adapted = _compatibility_document(document)
    normalized = normalize_draftkings_document(adapted, captured_at_utc=captured_at_utc)
    return [row for row in normalized if row.get("stat") == stat]


def _pair_summary(offers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pairs: dict[tuple[str, float], set[str]] = {}
    for row in offers:
        player = _clean(row.get("player_name"))
        line = row.get("line")
        side = (_clean(row.get("side")) or "").casefold()
        if not player or not isinstance(line, (int, float)) or side not in {"over", "under"}:
            continue
        key = (player.casefold(), float(line))
        pairs.setdefault(key, set()).add(side)
    paired = [key for key, sides in pairs.items() if {"over", "under"}.issubset(sides)]
    return {
        "unique_player_line_count": len(pairs),
        "two_sided_player_line_count": len(paired),
        "two_sided_offer_count": sum(2 for _ in paired),
    }


def _get(url: str, *, timeout_seconds: float, requester: Callable[..., Any] | None) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": "https://sportsbook.draftkings.com/leagues/basketball/wnba",
        "Origin": "https://sportsbook.draftkings.com",
    }
    if requester is not None:
        try:
            return requester(url, headers=headers, timeout=timeout_seconds)
        except TypeError:
            return requester("GET", url, headers=headers, timeout=timeout_seconds)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=False, headers=headers) as client:
        return client.get(url)


def probe_draftkings_wnba_prop_markets(
    candidates: Sequence[Mapping[str, Any]] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    environment = _environment(env)
    resolved = resolve_prop_candidates(candidates, env=environment)
    timeout_seconds = _timeout(environment)
    attempts: list[dict[str, Any]] = []

    for candidate in resolved:
        started = _now_iso()
        status: int | None = None
        document: Any | None = None
        response_error: str | None = None
        network_error_type: str | None = None
        try:
            response = _get(candidate["url"], timeout_seconds=timeout_seconds, requester=requester)
            status, document, response_error = _response_json(response)
        except Exception as exc:
            response_error = "request_failed"
            network_error_type = type(exc).__name__

        offers: list[dict[str, Any]] = []
        if isinstance(document, dict):
            try:
                offers = normalize_prop_candidate_document(
                    document,
                    expected_stat=candidate["expected_stat"],
                    captured_at_utc=started,
                )
            except Exception:
                offers = []
        pair_summary = _pair_summary(offers)
        identity = _document_wnba_identity(document)
        usable = bool(
            status == 200
            and response_error is None
            and identity
            and pair_summary["two_sided_player_line_count"] > 0
        )
        attempts.append(
            {
                **candidate,
                "host": (urlparse(candidate["url"]).hostname or "").casefold(),
                "started_at_utc": started,
                "http_status": status,
                "response_error": response_error,
                "network_error_type": network_error_type,
                "wnba_identity_verified": identity,
                "shape": _document_shape(document),
                "normalized_expected_stat_offer_count": len(offers),
                **pair_summary,
                "usable_for_step6d": usable,
            }
        )

    selected_by_stat: dict[str, dict[str, Any]] = {}
    for stat in REQUIRED_STATS:
        viable = [row for row in attempts if row["expected_stat"] == stat and row["usable_for_step6d"]]
        viable.sort(
            key=lambda row: (
                int(row["two_sided_player_line_count"]),
                int(row["normalized_expected_stat_offer_count"]),
                1 if row["family"] == "controlled_data_league_subcategory" else 0,
            ),
            reverse=True,
        )
        if viable:
            selected_by_stat[stat] = viable[0]

    all_verified = all(stat in selected_by_stat for stat in REQUIRED_STATS)
    selected_urls = [selected_by_stat[stat]["url"] for stat in REQUIRED_STATS if stat in selected_by_stat]
    exact_step6d_json = json.dumps(selected_urls, separators=(",", ":")) if all_verified else None
    selected_ids = {
        stat: {
            "family": selected_by_stat[stat]["family"],
            "category_id": selected_by_stat[stat]["category_id"] or None,
            "subcategory_id": selected_by_stat[stat]["subcategory_id"] or None,
        }
        for stat in REQUIRED_STATS
        if stat in selected_by_stat
    }
    fingerprint = _hash(
        {
            "wnba_league_id": WNBA_LEAGUE_ID,
            "attempts": attempts,
            "selected_ids": selected_ids,
            "all_required_stats_verified": all_verified,
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6f_draftkings_prop_market_probe",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "wnba_league_id": WNBA_LEAGUE_ID,
        "required_stats": list(REQUIRED_STATS),
        "live_probe_performed": True,
        "all_required_stats_verified": all_verified,
        "verified_stat_count": len(selected_by_stat),
        "selected_market_ids": selected_ids,
        "selected_by_stat": selected_by_stat,
        "step6d_configuration": {
            "env_name": "WNBA_DRAFTKINGS_MARKET_URLS_JSON",
            "generated": all_verified,
            "value": exact_step6d_json,
            "direct_sync_enablement_changed": False,
        },
        "attempts": attempts,
        "probe_fingerprint_sha256": fingerprint,
        "safety": {
            "http_methods": ["GET"],
            "authentication_used": False,
            "cookies_used": False,
            "sportsbook_account_required": False,
            "wager_action_performed": False,
            "paid_odds_vendor_used": False,
            "step_6d_auto_enabled": False,
            "production_runtime_enabled": False,
            "monte_carlo_run": False,
        },
    }
