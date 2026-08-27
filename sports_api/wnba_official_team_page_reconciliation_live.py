"""Step 6H live reconciliation using official WNBA team pages.

GitHub-hosted runners are challenged by the WNBA schedule CDN even when the
current URL is correct.  Official WNBA team home, schedule, and roster pages are
reachable with ordinary browser-compatible GET headers.  This adapter therefore
uses those pages as independent official evidence while preserving the Step 6H
fail-closed contract.

Important identity rule: team pages do not expose an official numeric WNBA game
ID consistently across all franchises.  This module never invents one.  It
creates a namespaced ``official_game_evidence_id`` solely for reconciliation
traceability and leaves ``official_game_id`` null.

This module is evidence-only: GET requests only, no production feed writes, no
scheduler/runtime activation, no paid odds vendor, no Monte Carlo, and no wager
action.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import date as date_type, timedelta
from html.parser import HTMLParser
import hashlib
import json
import os
from typing import Any
from urllib.parse import urlparse

import httpx

from sports_api.wnba_draftkings_shadow_ingestion import validate_shadow_feed
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_official_reconciliation import _iso_now, _name_key, _timeout
from sports_api.wnba_official_reconciliation_live import (
    TEAM_ROSTER_HOSTS,
    fetch_verified_draftkings_snapshot,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6H official team-page live reconciliation"
MODEL_VERSION = "wnba_step_6h_official_team_page_live_reconciliation_v1"
SCHEMA_VERSION = MODEL_VERSION
MAX_PAGE_BYTES = 5_000_000
UPCOMING_SECTION_CHARS = 18_000

_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

_DK_TEAM_ALIASES = {
    "atl dream": "Atlanta Dream",
    "atlanta dream": "Atlanta Dream",
    "chi sky": "Chicago Sky",
    "chicago sky": "Chicago Sky",
    "con sun": "Connecticut Sun",
    "connecticut sun": "Connecticut Sun",
    "dal wings": "Dallas Wings",
    "dallas wings": "Dallas Wings",
    "gs valkyries": "Golden State Valkyries",
    "gsv valkyries": "Golden State Valkyries",
    "golden state valkyries": "Golden State Valkyries",
    "ind fever": "Indiana Fever",
    "indiana fever": "Indiana Fever",
    "lv aces": "Las Vegas Aces",
    "lva aces": "Las Vegas Aces",
    "las vegas aces": "Las Vegas Aces",
    "la sparks": "Los Angeles Sparks",
    "las sparks": "Los Angeles Sparks",
    "los angeles sparks": "Los Angeles Sparks",
    "min lynx": "Minnesota Lynx",
    "minnesota lynx": "Minnesota Lynx",
    "ny liberty": "New York Liberty",
    "nyl liberty": "New York Liberty",
    "new york liberty": "New York Liberty",
    "pho mercury": "Phoenix Mercury",
    "phx mercury": "Phoenix Mercury",
    "phoenix mercury": "Phoenix Mercury",
    "por fire": "Portland Fire",
    "portland fire": "Portland Fire",
    "sea storm": "Seattle Storm",
    "seattle storm": "Seattle Storm",
    "tor tempo": "Toronto Tempo",
    "toronto tempo": "Toronto Tempo",
    "was mystics": "Washington Mystics",
    "washington mystics": "Washington Mystics",
}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data).strip()
        if text:
            self.parts.append(text)


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _registry(season: int) -> dict[str, dict[str, Any]]:
    return {
        _name_key(row["full_name"]): dict(row)
        for row in get_wnba_teams(int(season))
    }


def _resolve_team_name(value: Any, registry: Mapping[str, dict[str, Any]]) -> str | None:
    key = _name_key(value)
    if not key:
        return None
    if key in registry:
        return str(registry[key]["full_name"])
    alias = _DK_TEAM_ALIASES.get(key)
    if alias and _name_key(alias) in registry:
        return str(registry[_name_key(alias)]["full_name"])
    return None


def _event_teams(event: Mapping[str, Any], registry: Mapping[str, dict[str, Any]]) -> list[str]:
    resolved: list[str] = []
    for raw in event.get("participants") or []:
        team = _resolve_team_name(raw, registry)
        if team and team not in resolved:
            resolved.append(team)
    if len(resolved) != 2:
        name = str(event.get("event_name") or "")
        normalized = name.replace(" vs ", " @ ").replace(" VS ", " @ ")
        for raw in [part.strip() for part in normalized.split(" @ ") if part.strip()]:
            team = _resolve_team_name(raw, registry)
            if team and team not in resolved:
                resolved.append(team)
    return resolved[:2]


def _candidate_local_dates(utc_calendar_date: Any) -> list[str]:
    text = str(utc_calendar_date or "")[:10]
    try:
        utc_day = date_type.fromisoformat(text)
    except ValueError:
        return []
    # Late-evening North American games often roll to the following UTC date.
    # We expose this only as a reconciliation window, never as an official date.
    return [(utc_day - timedelta(days=1)).isoformat(), utc_day.isoformat()]


def _official_url(team_name: str, path: str) -> str:
    host = TEAM_ROSTER_HOSTS.get(_name_key(team_name))
    if not host:
        raise RuntimeError(f"No official WNBA host is registered for {team_name!r}.")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"https://{host}{suffix}"


def _fetch_page(
    team_name: str,
    path: str,
    *,
    timeout_seconds: float,
    requester: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    url = _official_url(team_name, path)
    try:
        if requester is not None:
            try:
                response = requester(url, headers=dict(_BROWSER_HEADERS), timeout=timeout_seconds)
            except TypeError:
                response = requester("GET", url, headers=dict(_BROWSER_HEADERS), timeout=timeout_seconds)
        else:
            with httpx.Client(
                timeout=timeout_seconds,
                follow_redirects=True,
                headers=_BROWSER_HEADERS,
            ) as client:
                response = client.get(url)
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        raise RuntimeError(f"Official WNBA page GET failed for {team_name} {path}.") from exc

    status = getattr(response, "status_code", None)
    if status != 200:
        raise RuntimeError(
            f"Official WNBA page returned HTTP {status if status is not None else 'unknown'} "
            f"for {team_name} {path}."
        )
    raw = getattr(response, "content", None)
    if raw is None:
        raw = str(getattr(response, "text", "")).encode("utf-8")
    if not isinstance(raw, (bytes, bytearray)) or not 0 < len(raw) <= MAX_PAGE_BYTES:
        raise RuntimeError(f"Official WNBA page size was invalid for {team_name} {path}.")

    parser = _VisibleTextParser()
    parser.feed(str(getattr(response, "text", "")))
    visible = _name_key(" ".join(parser.parts))
    if len(visible) < 20:
        raise RuntimeError(f"Official WNBA page text was unexpectedly short for {team_name} {path}.")
    return {
        "team_name": team_name,
        "host": (urlparse(url).hostname or "").casefold(),
        "path": path,
        "http_status": 200,
        "visible_text": f" {visible} ",
        "content_sha256": hashlib.sha256(bytes(raw)).hexdigest(),
    }


def _upcoming_text(page: Mapping[str, Any]) -> str:
    visible = str(page.get("visible_text") or "")
    for marker in (_name_key("Upcoming Games"), _name_key("Upcoming"), _name_key("Schedule")):
        start = visible.find(marker)
        if start >= 0:
            return visible[start : min(len(visible), start + UPCOMING_SECTION_CHARS)]
    return ""


def _roster_text(page: Mapping[str, Any]) -> str:
    visible = str(page.get("visible_text") or "")
    start_markers = (_name_key("2026 Team Roster"), _name_key("Team Roster"), _name_key("Roster"))
    start = -1
    used = ""
    for marker in start_markers:
        start = visible.find(marker)
        if start >= 0:
            used = marker
            break
    if start < 0:
        raise RuntimeError(f"Official WNBA roster marker was not found for {page.get('team_name')}.")
    end = visible.find(_name_key("Coaching Staff"), start + len(used))
    section = visible[start : end if end >= 0 else None]
    if len(section) < 40:
        raise RuntimeError(f"Official WNBA roster section was unexpectedly short for {page.get('team_name')}.")
    return f" {section} "


def _page_summary(page: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "team_name": page.get("team_name"),
        "host": page.get("host"),
        "path": page.get("path"),
        "http_status": page.get("http_status"),
        "content_sha256": page.get("content_sha256"),
    }


def reconcile_team_page_snapshot(
    draftkings: Mapping[str, Any],
    *,
    season: int,
    page_fetcher: Callable[[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    """Reconcile a proven DK shadow snapshot against official WNBA team pages."""
    shadow = validate_shadow_feed(dict(draftkings))
    offers = [dict(row) for row in draftkings.get("offers") or [] if isinstance(row, Mapping)]
    source_events = [
        dict(row) for row in draftkings.get("source_events") or [] if isinstance(row, Mapping)
    ]
    registry = _registry(int(season))
    blockers: list[str] = []
    mismatches: list[dict[str, Any]] = []
    if not shadow.get("ready_for_auto_sync"):
        blockers.append("step6g_shadow_validation_failed")
    if not offers:
        blockers.append("no_draftkings_offers")
    if not source_events:
        blockers.append("no_draftkings_events")

    event_meta = {
        str(row.get("source_event_id")): row
        for row in source_events
        if row.get("source_event_id")
    }
    events_by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    event_teams: dict[str, list[str]] = {}
    for event_id, event in event_meta.items():
        teams = _event_teams(event, registry)
        event_teams[event_id] = teams
        if len(teams) == 2:
            events_by_pair[tuple(sorted(_name_key(team) for team in teams))].append(event_id)

    page_cache: dict[tuple[str, str], Mapping[str, Any]] = {}

    def page(team: str, path: str) -> Mapping[str, Any]:
        key = (team, path)
        if key not in page_cache:
            page_cache[key] = page_fetcher(team, path)
        return page_cache[key]

    event_verifications: dict[str, dict[str, Any]] = {}
    for event_id, event in sorted(event_meta.items()):
        teams = event_teams.get(event_id) or []
        if len(teams) != 2:
            blockers.append("draftkings_event_team_pair_unresolved")
            mismatches.append(
                {
                    "type": "event_team_pair_unresolved",
                    "source_event_id": event_id,
                    "event_name": event.get("event_name"),
                }
            )
            event_verifications[event_id] = {
                "source_event_id": event_id,
                "verified": False,
                "reason": "team_pair_unresolved",
            }
            continue

        pair = tuple(sorted(_name_key(team) for team in teams))
        duplicate_market_pair = len(events_by_pair.get(pair) or []) != 1
        evidence_rows: list[dict[str, Any]] = []
        pair_confirmed = True
        upcoming_confirmed = True
        for team in teams:
            opponent = teams[1] if team == teams[0] else teams[0]
            root = page(team, "/")
            schedule = page(team, "/schedule")
            root_text = str(root.get("visible_text") or "")
            schedule_text = str(schedule.get("visible_text") or "")
            upcoming = _upcoming_text(root)
            opponent_key = _name_key(opponent)
            in_schedule = opponent_key in schedule_text
            in_upcoming = opponent_key in upcoming
            pair_confirmed = pair_confirmed and in_schedule
            upcoming_confirmed = upcoming_confirmed and in_upcoming
            evidence_rows.append(
                {
                    "team_name": team,
                    "opponent_name": opponent,
                    "official_home_host": root.get("host"),
                    "official_schedule_host": schedule.get("host"),
                    "home_http_status": root.get("http_status"),
                    "schedule_http_status": schedule.get("http_status"),
                    "opponent_in_official_schedule": in_schedule,
                    "opponent_in_official_upcoming": in_upcoming,
                    "home_content_sha256": root.get("content_sha256"),
                    "schedule_content_sha256": schedule.get("content_sha256"),
                }
            )

        verified = pair_confirmed and upcoming_confirmed and not duplicate_market_pair
        if not verified:
            blockers.append("official_event_near_term_pair_unverified")
            mismatches.append(
                {
                    "type": "event_near_term_pair_unverified",
                    "source_event_id": event_id,
                    "official_schedule_pair_confirmed": pair_confirmed,
                    "official_upcoming_pair_confirmed": upcoming_confirmed,
                    "duplicate_draftkings_pair": duplicate_market_pair,
                }
            )

        evidence_identity = {
            "source_event_id": event_id,
            "teams": sorted(teams),
            "candidate_local_dates": _candidate_local_dates(event.get("event_date")),
            "evidence": evidence_rows,
        }
        evidence_id = f"team-schedule:{_hash(evidence_identity)[:32]}"
        event_verifications[event_id] = {
            "source_event_id": event_id,
            "verified": verified,
            "official_game_id": None,
            "official_game_evidence_id": evidence_id,
            "official_game_id_available": False,
            "verification_mode": "mutual_official_team_pages_unique_near_term_match",
            "draftkings_utc_calendar_date": event.get("event_date"),
            "candidate_local_date_window": _candidate_local_dates(event.get("event_date")),
            "official_game_date": None,
            "official_game_date_claimed": False,
            "team_names": teams,
            "official_schedule_pair_confirmed": pair_confirmed,
            "official_upcoming_pair_confirmed": upcoming_confirmed,
            "unique_draftkings_team_pair": not duplicate_market_pair,
            "official_evidence": evidence_rows,
        }

    players_for_event: dict[str, set[str]] = defaultdict(set)
    display_name_by_key: dict[str, str] = {}
    for offer in offers:
        event_id = str(offer.get("source_event_id") or "")
        player_name = str(offer.get("player_name") or "").strip()
        player_key = _name_key(player_name)
        if event_id and player_key:
            players_for_event[event_id].add(player_key)
            display_name_by_key.setdefault(player_key, player_name)

    roster_cache: dict[str, str] = {}
    player_team_matches: dict[tuple[str, str], list[str]] = {}
    for event_id, player_keys in players_for_event.items():
        teams = event_teams.get(event_id) or []
        if len(teams) != 2:
            continue
        for team in teams:
            if team not in roster_cache:
                roster_cache[team] = _roster_text(page(team, "/roster"))
        for player_key in player_keys:
            matches = [team for team in teams if f" {player_key} " in roster_cache[team]]
            player_team_matches[(event_id, player_key)] = matches

    player_verifications: list[dict[str, Any]] = []
    verified_player_keys: set[str] = set()
    verified_player_event_pairs: set[tuple[str, str]] = set()
    for event_id in sorted(players_for_event):
        for player_key in sorted(players_for_event[event_id]):
            player_name = display_name_by_key.get(player_key, player_key)
            matches = player_team_matches.get((event_id, player_key), [])
            event_ok = bool((event_verifications.get(event_id) or {}).get("verified"))
            verified = len(matches) == 1 and event_ok
            if len(matches) != 1:
                blockers.append("official_current_roster_membership_unverified")
                mismatches.append(
                    {
                        "type": "player_roster_membership_unverified",
                        "source_event_id": event_id,
                        "player_name": player_name,
                        "official_team_match_count": len(matches),
                        "candidate_team_names": matches,
                    }
                )
            elif not event_ok:
                blockers.append("market_player_game_consistency_failed")
            if verified:
                verified_player_keys.add(player_key)
                verified_player_event_pairs.add((event_id, player_key))
            matched_team = matches[0] if len(matches) == 1 else None
            roster_page = page(matched_team, "/roster") if matched_team else None
            player_verifications.append(
                {
                    "source_event_id": event_id,
                    "player_name": player_name,
                    "player_key": player_key,
                    "verified": verified,
                    "official_player_id": None,
                    "official_player_id_available": False,
                    "verified_team_name": matched_team,
                    "verified_team_key": _name_key(matched_team) if matched_team else None,
                    "roster_source": "official_wnba_team_roster_page",
                    "roster_host": roster_page.get("host") if roster_page else None,
                    "roster_content_sha256": roster_page.get("content_sha256") if roster_page else None,
                }
            )

    # Every normalized offer must resolve to a verified player/event pair.
    offer_consistency_failures = 0
    for offer in offers:
        event_id = str(offer.get("source_event_id") or "")
        player_key = _name_key(offer.get("player_name"))
        if not event_id or not player_key or (event_id, player_key) not in verified_player_event_pairs:
            offer_consistency_failures += 1
    if offer_consistency_failures:
        blockers.append("market_player_game_consistency_failed")
        mismatches.append(
            {
                "type": "offer_player_game_consistency_failures",
                "failure_count": offer_consistency_failures,
            }
        )

    verified_event_count = sum(1 for row in event_verifications.values() if row.get("verified"))
    unique_markets = {
        str(row.get("source_market_id"))
        for row in offers
        if row.get("source_market_id")
    }
    all_events_verified = bool(event_verifications) and verified_event_count == len(event_verifications)
    all_players_verified = bool(player_verifications) and all(row.get("verified") for row in player_verifications)
    ready = (
        bool(shadow.get("ready_for_auto_sync"))
        and all_events_verified
        and all_players_verified
        and offer_consistency_failures == 0
        and not blockers
    )

    fingerprint_identity = {
        "date": draftkings.get("date"),
        "season": int(season),
        "source_offer_ids": sorted(
            str(row.get("source_offer_id")) for row in offers if row.get("source_offer_id")
        ),
        "players": sorted(
            (
                row.get("source_event_id"),
                row.get("player_key"),
                row.get("verified_team_key"),
                row.get("verified"),
            )
            for row in player_verifications
        ),
        "events": sorted(
            (
                event_id,
                row.get("verified"),
                row.get("official_game_evidence_id"),
                tuple(row.get("candidate_local_date_window") or []),
            )
            for event_id, row in event_verifications.items()
        ),
        "blockers": sorted(set(blockers)),
        "ready_for_auto_sync": ready,
    }

    page_summaries = [
        _page_summary(value)
        for _, value in sorted(page_cache.items(), key=lambda item: item[0])
    ]
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6h_official_team_page_live_reconciliation",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "date": draftkings.get("date"),
        "season": int(season),
        "offer_side_count": len(offers),
        "market_count": len(unique_markets),
        "draftkings_event_count": len(event_verifications),
        "verified_player_count": len(verified_player_keys),
        "verified_roster_membership_count": len(verified_player_keys),
        "verified_event_count": verified_event_count,
        "verified_market_count": len(unique_markets) if ready else 0,
        "player_verifications": sorted(
            player_verifications,
            key=lambda row: (str(row.get("source_event_id")), _name_key(row.get("player_name"))),
        ),
        "event_verifications": [event_verifications[key] for key in sorted(event_verifications)],
        "mismatch_details": mismatches,
        "blockers": sorted(set(blockers)),
        "step6g_shadow_ready": bool(shadow.get("ready_for_auto_sync")),
        "step6g_blockers": list(shadow.get("blockers") or []),
        "ready_for_auto_sync": ready,
        "reconciliation_fingerprint_sha256": _hash(fingerprint_identity),
        "official_source_summary": {
            "verification_mode": "mutual official WNBA team home + schedule + roster pages",
            "numeric_game_id_required": False,
            "numeric_game_id_fabricated": False,
            "official_local_game_date_claimed": False,
            "page_reads": page_summaries,
        },
        "safety": {
            "http_methods": ["GET"],
            "authentication_used": False,
            "cookies_used": False,
            "production_feed_written": False,
            "direct_sync_enablement_changed": False,
            "production_runtime_enablement_changed": False,
            "scheduler_enablement_changed": False,
            "paid_odds_vendor_used": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
        },
    }


def run_live_official_reconciliation(
    *,
    date: str,
    season: int,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    environment = os.environ if env is None else env
    timeout_seconds = _timeout(environment)
    draftkings = fetch_verified_draftkings_snapshot(
        date=str(date),
        season=int(season),
        env=environment,
    )

    def fetch(team_name: str, path: str) -> Mapping[str, Any]:
        return _fetch_page(
            team_name,
            path,
            timeout_seconds=timeout_seconds,
            requester=requester,
        )

    report = reconcile_team_page_snapshot(
        draftkings,
        season=int(season),
        page_fetcher=fetch,
    )
    report["draftkings_source_summary"] = list(draftkings.get("source_summary") or [])
    return report
