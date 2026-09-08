"""College Football Schedule V1 — Step 2 official schedule + game identity.

Primary identity source:
- NCAA's current public schedule GraphQL endpoint (FBS / MFB / division 11).

Secondary enrichment:
- ESPN's public College Football scoreboard for venue/status/provider IDs only.

The module is intentionally schedule/identity-only. It does not calculate win
probabilities, projected scores, totals, fair odds, picks, or simulations.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import requests
import streamlit as st

MODEL_VERSION = "CFB SCHEDULE V1 • STEP 2 OFFICIAL SCHEDULE + GAME IDENTITY"

NCAA_SCHEDULE_URL = "https://sdataprod.ncaa.com/"
NCAA_SCHEDULE_QUERY_NAME = "NCAA_schedules_today_web"
NCAA_SCHEDULE_HASH = "a25ad021179ce1d97fb951a49954dc98da150089f9766e7e85890e439516ffbf"
NCAA_SPORT_CODE = "MFB"
NCAA_FBS_DIVISION = 11

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
)

_ET = ZoneInfo("America/New_York")
_USER_AGENT = "KyreSportsAI/CFB-Step2"
_TIMEOUT = 18


def _day(value: Any) -> str:
    """Normalize a date-like input to YYYY-MM-DD."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        raise ValueError("A CFB schedule date is required")
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt != "%Y%m%d" else text[:8], fmt).date().isoformat()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except Exception as exc:
        raise ValueError(f"Unsupported CFB schedule date: {value!r}") from exc


def _season_year(day: str) -> int:
    d = datetime.strptime(_day(day), "%Y-%m-%d").date()
    return d.year - 1 if d.month < 7 else d.year


def _wire_get_requests(url: str, params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    r = requests.get(
        url,
        params=dict(params),
        timeout=_TIMEOUT,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    meta = {
        "transport": "requests",
        "http": int(r.status_code),
        "bytes": len(r.content or b""),
        "url": str(getattr(r, "url", url)),
    }
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, dict):
        raise ValueError("Provider returned a non-object JSON payload")
    return payload, meta


def _wire_get_urllib(url: str, params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    full = url + ("?" + urlencode(dict(params)) if params else "")
    req = Request(
        full,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(req, timeout=_TIMEOUT) as response:
        raw = response.read()
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Provider returned a non-object JSON payload")
        return payload, {
            "transport": "urllib",
            "http": int(getattr(response, "status", 200)),
            "bytes": len(raw),
            "url": full,
        }


def _fetch_json_with_fallback(
    url: str,
    params: Mapping[str, Any],
    provider: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for transport, fn in (("requests", _wire_get_requests), ("urllib", _wire_get_urllib)):
        try:
            payload, wire = fn(url, params)
            attempts.append(
                {
                    "provider": provider,
                    "transport": transport,
                    "http": wire.get("http"),
                    "bytes": wire.get("bytes"),
                    "error": "",
                }
            )
            return payload, attempts
        except Exception as exc:
            attempts.append(
                {
                    "provider": provider,
                    "transport": transport,
                    "http": None,
                    "bytes": 0,
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                }
            )
    return {}, attempts


def _ncaa_params(season_year: int) -> dict[str, str]:
    variables = {
        "sportCode": NCAA_SPORT_CODE,
        "division": NCAA_FBS_DIVISION,
        "seasonYear": int(season_year),
    }
    extensions = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": NCAA_SCHEDULE_HASH,
        }
    }
    return {
        "extensions": json.dumps(extensions, separators=(",", ":")),
        "queryName": NCAA_SCHEDULE_QUERY_NAME,
        "variables": json.dumps(variables, separators=(",", ":")),
    }


def _walk_contests(node: Any) -> Iterable[dict[str, Any]]:
    """Yield contest-shaped dictionaries no matter how NCAA nests the schedule."""
    if isinstance(node, dict):
        teams = node.get("teams")
        has_identity = node.get("contestId") is not None or node.get("contestID") is not None
        if isinstance(teams, list) and has_identity:
            yield node
        for value in node.values():
            yield from _walk_contests(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_contests(item)


def _clean_text(value: Any, fallback: str = "") -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or fallback


def _slug(value: Any) -> str:
    text = _clean_text(value).lower()
    text = text.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _name_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_text(value).lower())


def _safe_epoch(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text or not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None
    try:
        raw = float(text)
        if raw > 10_000_000_000:
            raw /= 1000.0
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    except Exception:
        return None


def _contest_datetime(contest: Mapping[str, Any]) -> datetime | None:
    epoch = _safe_epoch(contest.get("startTimeEpoch"))
    if epoch is not None:
        return epoch.astimezone(_ET)

    start_date = _clean_text(contest.get("startDate"))
    start_time = _clean_text(contest.get("startTime"))
    cleaned_time = re.sub(r"\b(?:ET|EST|EDT)\b", "", start_time, flags=re.I).strip()

    candidates = []
    if start_date and cleaned_time:
        candidates.append(f"{start_date} {cleaned_time}")
    if start_date:
        candidates.append(start_date)

    formats = (
        "%Y-%m-%d %I:%M %p",
        "%m/%d/%Y %I:%M %p",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y",
    )
    for text in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=_ET)
            except Exception:
                pass

    for key in ("startDateTime", "date"):
        text = _clean_text(contest.get(key))
        if not text:
            continue
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=_ET)
            return parsed.astimezone(_ET)
        except Exception:
            pass
    return None


def _team_side(contest: Mapping[str, Any], is_home: bool) -> dict[str, Any]:
    for team in contest.get("teams") or []:
        if not isinstance(team, dict):
            continue
        if bool(team.get("isHome")) != bool(is_home):
            continue
        name = _clean_text(
            team.get("nameShort")
            or team.get("name6Char")
            or team.get("name")
            or team.get("displayName"),
            "Home" if is_home else "Away",
        )
        seo = _clean_text(team.get("seoname") or team.get("seoName") or _slug(name))
        conference = _clean_text(
            team.get("conferenceSeo")
            or team.get("conference")
            or team.get("conferenceName"),
            "Conference unavailable",
        )
        return {
            "name": name,
            "slug": seo,
            "conference": conference,
            "rank": team.get("teamRank"),
        }
    return {}


def _ncaa_status(contest: Mapping[str, Any]) -> str:
    final_message = _clean_text(contest.get("finalMessage"))
    if final_message:
        return final_message
    state = _clean_text(contest.get("gameState")).upper()
    if state == "F":
        return "Final"
    if state == "I":
        return "In Progress"
    if state == "P":
        return "Scheduled"
    return "Status unavailable"


def _official_game(contest: Mapping[str, Any], requested_day: str) -> dict[str, Any] | None:
    contest_id = _clean_text(contest.get("contestId") or contest.get("contestID"))
    if not contest_id:
        return None

    home = _team_side(contest, True)
    away = _team_side(contest, False)
    if not home or not away:
        return None

    kickoff = _contest_datetime(contest)
    if kickoff is None:
        start_date = _clean_text(contest.get("startDate"))
        try:
            kickoff = datetime.fromisoformat(_day(start_date)).replace(tzinfo=_ET)
        except Exception:
            return None

    game_day = kickoff.astimezone(_ET).date().isoformat()
    if game_day != requested_day:
        return None

    home_slug = _clean_text(home.get("slug")) or _slug(home.get("name"))
    away_slug = _clean_text(away.get("slug")) or _slug(away.get("name"))
    if not home_slug or not away_slug:
        return None

    identity_payload = f"{contest_id}|{away_slug}|{home_slug}".encode("utf-8")
    fingerprint = hashlib.sha256(identity_payload).hexdigest()[:20]
    kickoff_text = kickoff.strftime("%I:%M %p").lstrip("0") + " ET"

    return {
        "game_id": contest_id,
        "identity_key": f"ncaa:{contest_id}",
        "identity_fingerprint": fingerprint,
        "game_date": game_day,
        "kickoff_et": kickoff_text,
        "kickoff_iso": kickoff.isoformat(),
        "away_team": _clean_text(away.get("name"), "Away"),
        "away_team_slug": away_slug,
        "away_conference": _clean_text(away.get("conference"), "Conference unavailable"),
        "away_rank": away.get("rank"),
        "home_team": _clean_text(home.get("name"), "Home"),
        "home_team_slug": home_slug,
        "home_conference": _clean_text(home.get("conference"), "Conference unavailable"),
        "home_rank": home.get("rank"),
        "venue": "Venue unavailable",
        "status": _ncaa_status(contest),
        "broadcast": _clean_text(contest.get("broadcasterName"), "Broadcast unavailable"),
        "neutral_site": bool(contest.get("neutralSite") or contest.get("isNeutralSite")),
        "ncaa_url": _clean_text(contest.get("url")),
        "espn_event_id": "",
        "schedule_source": "NCAA official schedule GraphQL",
        "enrichment_source": "none",
        "identity_verified": True,
        "date_matches_query": True,
    }


def _espn_team_names(competitor: Mapping[str, Any]) -> set[str]:
    team = competitor.get("team") or {}
    values = {
        team.get("displayName"),
        team.get("shortDisplayName"),
        team.get("location"),
        team.get("name"),
        team.get("nickname"),
        team.get("slug"),
    }
    return {_name_key(v) for v in values if _name_key(v)}


def _espn_index(payload: Mapping[str, Any], requested_day: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        competitions = event.get("competitions") or []
        if not competitions or not isinstance(competitions[0], dict):
            continue
        comp = competitions[0]
        sides: dict[str, dict[str, Any]] = {}
        for competitor in comp.get("competitors") or []:
            if isinstance(competitor, dict):
                sides[_clean_text(competitor.get("homeAway")).lower()] = competitor
        home = sides.get("home") or {}
        away = sides.get("away") or {}
        if not home or not away:
            continue

        raw_date = _clean_text(event.get("date") or comp.get("date"))
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            game_day = dt.astimezone(_ET).date().isoformat()
        except Exception:
            game_day = requested_day
        if game_day != requested_day:
            continue

        status_type = (event.get("status") or {}).get("type") or {}
        rows.append(
            {
                "event_id": _clean_text(event.get("id")),
                "home_names": _espn_team_names(home),
                "away_names": _espn_team_names(away),
                "venue": _clean_text((comp.get("venue") or {}).get("fullName")),
                "status": _clean_text(
                    status_type.get("description")
                    or status_type.get("detail")
                    or status_type.get("shortDetail")
                ),
            }
        )
    return rows


def _game_name_keys(game: Mapping[str, Any], side: str) -> set[str]:
    name = _clean_text(game.get(f"{side}_team"))
    slug = _clean_text(game.get(f"{side}_team_slug"))
    out = {_name_key(name), _name_key(slug), _name_key(slug.replace("-", " "))}
    tokens = re.split(r"[-\s]+", slug.lower())
    if len(tokens) >= 2:
        out.add(_name_key(" ".join(tokens)))
    return {v for v in out if v}


def _names_overlap(a: set[str], b: set[str]) -> bool:
    if a & b:
        return True
    for left in a:
        for right in b:
            if len(left) >= 6 and len(right) >= 6 and (left in right or right in left):
                return True
    return False


def _enrich_with_espn(
    games: list[dict[str, Any]],
    payload: Mapping[str, Any],
    requested_day: str,
) -> int:
    rows = _espn_index(payload, requested_day)
    matched = 0
    used: set[str] = set()
    for game in games:
        home_keys = _game_name_keys(game, "home")
        away_keys = _game_name_keys(game, "away")
        candidate = None
        for row in rows:
            if row.get("event_id") in used:
                continue
            if _names_overlap(home_keys, row.get("home_names") or set()) and _names_overlap(
                away_keys, row.get("away_names") or set()
            ):
                candidate = row
                break
        if candidate is None:
            continue
        used.add(str(candidate.get("event_id") or ""))
        matched += 1
        if candidate.get("venue"):
            game["venue"] = candidate["venue"]
        if candidate.get("status") and game.get("status") in {
            "Scheduled",
            "Status unavailable",
        }:
            game["status"] = candidate["status"]
        game["espn_event_id"] = str(candidate.get("event_id") or "")
        game["enrichment_source"] = "ESPN College Football scoreboard"
    return matched


def _dedupe_official(games: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_id: dict[str, dict[str, Any]] = {}
    duplicate_ids = 0
    for game in games:
        gid = str(game.get("game_id") or "")
        if gid in by_id:
            duplicate_ids += 1
            continue
        by_id[gid] = game

    unique: list[dict[str, Any]] = []
    seen_natural: set[tuple[str, str, str, str]] = set()
    duplicate_natural = 0
    for game in sorted(by_id.values(), key=lambda g: (str(g.get("kickoff_iso")), str(g.get("game_id")))):
        natural = (
            str(game.get("game_date")),
            _name_key(game.get("away_team_slug")),
            _name_key(game.get("home_team_slug")),
            str(game.get("kickoff_iso")),
        )
        if natural in seen_natural:
            duplicate_natural += 1
            continue
        seen_natural.add(natural)
        unique.append(game)
    return unique, {
        "duplicate_event_ids_dropped": duplicate_ids,
        "duplicate_identity_rows_dropped": duplicate_natural,
    }


def _parse_ncaa_schedule(payload: Mapping[str, Any], requested_day: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    raw_contests = list(_walk_contests(payload))
    parsed: list[dict[str, Any]] = []
    malformed = 0
    off_date = 0
    for contest in raw_contests:
        game = _official_game(contest, requested_day)
        if game is None:
            dt = _contest_datetime(contest)
            if dt is not None and dt.astimezone(_ET).date().isoformat() != requested_day:
                off_date += 1
            else:
                malformed += 1
            continue
        parsed.append(game)
    deduped, dup_diag = _dedupe_official(parsed)
    return deduped, {
        "raw_contests": len(raw_contests),
        "off_date_contests_ignored": off_date,
        "malformed_contests_ignored": malformed,
        **dup_diag,
    }


@st.cache_data(ttl=120, show_spinner=False)
def load_with_diagnostics(target_date: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load one FBS slate from NCAA, then safely enrich venue/status from ESPN."""
    requested_day = _day(target_date)
    season_year = _season_year(requested_day)
    attempts: list[dict[str, Any]] = []

    ncaa_payload, ncaa_attempts = _fetch_json_with_fallback(
        NCAA_SCHEDULE_URL,
        _ncaa_params(season_year),
        "NCAA official schedule",
    )
    attempts.extend(ncaa_attempts)
    games, parse_diag = _parse_ncaa_schedule(ncaa_payload, requested_day) if ncaa_payload else ([], {
        "raw_contests": 0,
        "off_date_contests_ignored": 0,
        "malformed_contests_ignored": 0,
        "duplicate_event_ids_dropped": 0,
        "duplicate_identity_rows_dropped": 0,
    })

    espn_matched = 0
    if games:
        espn_payload, espn_attempts = _fetch_json_with_fallback(
            ESPN_SCOREBOARD_URL,
            {
                "dates": requested_day.replace("-", ""),
                "limit": 500,
                "groups": 80,
            },
            "ESPN CFB enrichment",
        )
        attempts.extend(espn_attempts)
        if espn_payload:
            espn_matched = _enrich_with_espn(games, espn_payload, requested_day)

    venue_missing = sum(1 for g in games if g.get("venue") == "Venue unavailable")
    conference_missing = sum(
        int(g.get("away_conference") == "Conference unavailable")
        + int(g.get("home_conference") == "Conference unavailable")
        for g in games
    )
    ready = bool(games) and all(bool(g.get("identity_verified")) for g in games)

    diag = {
        "version": MODEL_VERSION,
        "requested_date": requested_day,
        "season_year": season_year,
        "source": "NCAA official schedule GraphQL" if games else "none",
        "enrichment": "ESPN College Football scoreboard" if espn_matched else "none",
        "games": len(games),
        "identity_ready": ready,
        "espn_matches": espn_matched,
        "venue_missing": venue_missing,
        "conference_fields_missing": conference_missing,
        "attempts": attempts,
        **parse_diag,
    }
    return games, diag


@st.cache_data(ttl=120, show_spinner=False)
def games_for_date(target_date: Any) -> list[dict[str, Any]]:
    games, _ = load_with_diagnostics(target_date)
    return games


def clear_schedule_cache() -> None:
    for fn in (games_for_date, load_with_diagnostics):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "ESPN_SCOREBOARD_URL",
    "MODEL_VERSION",
    "NCAA_FBS_DIVISION",
    "NCAA_SCHEDULE_HASH",
    "NCAA_SCHEDULE_QUERY_NAME",
    "NCAA_SCHEDULE_URL",
    "NCAA_SPORT_CODE",
    "_dedupe_official",
    "_enrich_with_espn",
    "_ncaa_params",
    "_parse_ncaa_schedule",
    "clear_schedule_cache",
    "games_for_date",
    "load_with_diagnostics",
]
