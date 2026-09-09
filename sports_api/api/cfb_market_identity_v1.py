"""College Football market identity reconciliation — odds integration Step 2.

This layer attaches provider market rows from Step 1 to verified College
Football game identities. Sportsbook data is market context only and carries
0% projection weight.

Identity sources:
- preferred: the verified CFB runtime snapshot when it exists on the host;
- production fallback: ESPN's CFB scoreboard for the exact market dates.

Matching is deterministic and fail-closed. No synthetic game IDs are created
and no fuzzy/name-only cross-date guess is allowed.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import unicodedata
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
import httpx

from sports_api.api.cfb_markets import _load_feed

router = APIRouter(prefix="/api/v1/cfb/markets", tags=["cfb"])

MODEL_VERSION = "CFB MARKET IDENTITY V1 • ODDS INTEGRATION STEP 2"
SNAPSHOT_PATH_ENV = "CFB_VERIFIED_SNAPSHOT_PATH"
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "cfb_runtime_snapshot_v1.json"
)
ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/"
    "college-football/scoreboard"
)
GITHUB_VERIFIED_SNAPSHOT_URL_ENV = "CFB_GITHUB_VERIFIED_SNAPSHOT_URL"
DEFAULT_GITHUB_VERIFIED_SNAPSHOT_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    "main/data/cfb_runtime_snapshot_v1.json"
)
MATCH_THRESHOLD = 0.88
AMBIGUITY_MARGIN = 0.08
_HTTP_TIMEOUT = 12.0
_ET = ZoneInfo("America/New_York")

_GENERIC_TOKENS = {
    "the",
    "university",
    "college",
    "football",
    "team",
}

_TOKEN_REPLACEMENTS = {
    "st": "state",
    "st.": "state",
}

_EXACT_ALIASES = {
    "southern california": "usc",
    "southern california trojans": "usc",
    "usc trojans": "usc",
    "connecticut": "uconn",
    "connecticut huskies": "uconn",
    "uconn huskies": "uconn",
    "central florida": "ucf",
    "central florida knights": "ucf",
    "ucf knights": "ucf",
    "southern methodist": "smu",
    "southern methodist mustangs": "smu",
    "smu mustangs": "smu",
    "brigham young": "byu",
    "brigham young cougars": "byu",
    "byu cougars": "byu",
    "texas christian": "tcu",
    "texas christian horned frogs": "tcu",
    "tcu horned frogs": "tcu",
    "north carolina state": "nc state",
    "north carolina state wolfpack": "nc state",
    "nc state wolfpack": "nc state",
    "mississippi rebels": "ole miss",
    "ole miss rebels": "ole miss",
    # Verified live FanDuel <-> ESPN CFB naming differences.
    "miami florida": "miami",
    "miami hurricanes": "miami",
    "miami florida hurricanes": "miami",
    "appalachian state": "app state",
    "appalachian state mountaineers": "app state",
    "app state mountaineers": "app state",
    "albany": "ualbany",
    "albany great danes": "ualbany",
    "ualbany great danes": "ualbany",
    "miami ohio": "miami oh",
    "miami oh redhawks": "miami oh",
    "fiu": "florida international",
    "fiu panthers": "florida international",
    "florida international panthers": "florida international",
    "sam houston state": "sam houston",
    "sam houston state bearkats": "sam houston",
    "sam houston bearkats": "sam houston",
    "utrgv": "ut rio grande valley",
    "ut rio grande valley vaqueros": "ut rio grande valley",
    "hawai i": "hawaii",
    "hawai i rainbow warriors": "hawaii",
    "hawaii rainbow warriors": "hawaii",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _ascii(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean(value))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _normalized_text(value: Any) -> str:
    text = _ascii(value).casefold().replace("&", " and ")
    text = re.sub(r"\(([^)]*)\)", r" \1 ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _EXACT_ALIASES.get(text, text)


def _tokens(value: Any) -> tuple[str, ...]:
    text = _normalized_text(value)
    tokens: list[str] = []
    for raw in text.split():
        token = _TOKEN_REPLACEMENTS.get(raw, raw)
        if token and token not in _GENERIC_TOKENS:
            tokens.append(token)
    return tuple(tokens)


def _name_score(provider_name: Any, verified_name: Any) -> float:
    """Return a deterministic school-name agreement score in [0, 1]."""
    p_text = _normalized_text(provider_name)
    v_text = _normalized_text(verified_name)
    if not p_text or not v_text:
        return 0.0
    if p_text == v_text:
        return 1.0

    p = set(_tokens(provider_name))
    v = set(_tokens(verified_name))
    if not p or not v:
        return 0.0
    if p == v:
        return 1.0

    # Sportsbooks commonly append mascots. Requiring all shorter school/location
    # tokens to be contained in the longer name keeps the match deterministic.
    if v.issubset(p):
        return 0.98 if len(v) >= 2 else 0.90
    if p.issubset(v):
        return 0.96 if len(p) >= 2 else 0.88

    overlap = len(p & v)
    union = len(p | v)
    if not union:
        return 0.0
    jaccard = overlap / union
    containment = overlap / min(len(p), len(v))
    return round((0.55 * containment) + (0.45 * jaccard), 6)


def _parse_market_date(start_time_utc: Any) -> str:
    text = _clean(start_time_utc)
    if not text:
        raise ValueError("start_time_utc is required for identity reconciliation")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("start_time_utc must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("start_time_utc must include a timezone")
    return parsed.astimezone(_ET).date().isoformat()


def _snapshot_path() -> Path:
    configured = _clean(os.environ.get(SNAPSHOT_PATH_ENV))
    if not configured:
        return DEFAULT_SNAPSHOT_PATH
    path = Path(configured).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{SNAPSHOT_PATH_ENV} must be an absolute path")
    return path


def _normalize_verified_game(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    event_id = _clean(row.get("event_id"))
    game_date = _clean(row.get("game_date"))
    away_team = _clean(row.get("away_team"))
    home_team = _clean(row.get("home_team"))
    if not event_id or not game_date or not away_team or not home_team:
        return None

    away = row.get("away") if isinstance(row.get("away"), dict) else {}
    home = row.get("home") if isinstance(row.get("home"), dict) else {}
    return {
        "event_id": event_id,
        "game_date": game_date,
        "away_team": away_team,
        "home_team": home_team,
        "away_team_id": _clean(row.get("away_team_id") or away.get("team_id")),
        "home_team_id": _clean(row.get("home_team_id") or home.get("team_id")),
        "venue": _clean(row.get("venue")),
        "broadcast": _clean(row.get("broadcast")),
        "status": _clean(row.get("status")),
        "sources": list(row.get("sources") or []),
    }


def load_verified_games() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load the local verified runtime snapshot when the shared host has it.

    The API production branch intentionally does not require this file. When it
    is absent, reconciliation first reads the public GitHub runtime snapshot
    maintained by the existing hourly GitHub Actions refresh, then uses direct
    ESPN exact-date reads only as a final fail-closed fallback.
    """
    path = _snapshot_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [], {
            "snapshot_present": False,
            "snapshot_path_configured": bool(_clean(os.environ.get(SNAPSHOT_PATH_ENV))),
            "verified_games": 0,
            "resolver_fallback": "ESPN CFB FBS/FCS scoreboards by exact market date",
        }
    except OSError as exc:
        return [], {
            "snapshot_present": False,
            "snapshot_error": f"{type(exc).__name__}: {exc}"[:240],
            "verified_games": 0,
            "resolver_fallback": "ESPN CFB scoreboard by exact market date",
        }

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("verified CFB runtime snapshot is invalid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
        raise ValueError("verified CFB runtime snapshot has an invalid contract")

    games: list[dict[str, Any]] = []
    malformed = 0
    seen_ids: set[str] = set()
    duplicate_ids = 0
    for row in payload["games"]:
        game = _normalize_verified_game(row)
        if game is None:
            malformed += 1
            continue
        if game["event_id"] in seen_ids:
            duplicate_ids += 1
            continue
        seen_ids.add(game["event_id"])
        games.append(game)

    return games, {
        "snapshot_present": True,
        "snapshot_version": payload.get("version"),
        "snapshot_generated_at": payload.get("generated_at"),
        "snapshot_window": payload.get("window"),
        "verified_games": len(games),
        "malformed_games_ignored": malformed,
        "duplicate_event_ids_ignored": duplicate_ids,
    }


def _github_snapshot_url() -> str:
    configured = _clean(os.environ.get(GITHUB_VERIFIED_SNAPSHOT_URL_ENV))
    return configured or DEFAULT_GITHUB_VERIFIED_SNAPSHOT_URL


def _github_verified_games_from_payload(
    payload: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    games_raw = payload.get("games")
    if not isinstance(games_raw, list):
        raise ValueError("GitHub CFB runtime snapshot has an invalid games contract")

    games: list[dict[str, Any]] = []
    malformed = 0
    duplicate_ids = 0
    seen: set[str] = set()
    for row in games_raw:
        game = _normalize_verified_game(row)
        if game is None:
            malformed += 1
            continue
        event_id = _clean(game.get("event_id"))
        if event_id in seen:
            duplicate_ids += 1
            continue
        seen.add(event_id)
        games.append(game)

    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    return games, {
        "source": "GitHub hourly CFB runtime snapshot",
        "snapshot_version": payload.get("version"),
        "snapshot_generated_at": payload.get("generated_at"),
        "snapshot_window": window,
        "verified_games": len(games),
        "malformed_games_ignored": malformed,
        "duplicate_event_ids_ignored": duplicate_ids,
        "synthetic_ids": False,
        "fuzzy_matching": False,
    }


def _fetch_github_verified_games() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = _github_snapshot_url()
    try:
        response = httpx.get(
            url,
            timeout=_HTTP_TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; KyreSportsAPI-CFB-Identity/1.0)"
                ),
                "Accept": "application/json,text/plain,*/*",
                "Cache-Control": "no-cache",
            },
            follow_redirects=True,
        )
        status_code = int(response.status_code)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("GitHub CFB runtime snapshot returned a non-object payload")
        games, diag = _github_verified_games_from_payload(payload)
        return games, {
            **diag,
            "http": status_code,
            "ok": True,
            "url_configured": bool(
                _clean(os.environ.get(GITHUB_VERIFIED_SNAPSHOT_URL_ENV))
            ),
        }
    except Exception as exc:
        return [], {
            "source": "GitHub hourly CFB runtime snapshot",
            "http": None,
            "ok": False,
            "verified_games": 0,
            "url_configured": bool(
                _clean(os.environ.get(GITHUB_VERIFIED_SNAPSHOT_URL_ENV))
            ),
            "error": f"{type(exc).__name__}: {exc}"[:300],
            "fail_closed": True,
        }


def _espn_game_date(raw_date: Any, requested_day: str) -> str:
    text = _clean(raw_date)
    if not text:
        return requested_day
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return requested_day
        return parsed.astimezone(_ET).date().isoformat()
    except ValueError:
        return requested_day


def _espn_verified_games_from_payload(
    payload: Mapping[str, Any],
    requested_day: str,
) -> list[dict[str, Any]]:
    games: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        event_id = _clean(event.get("id"))
        competitions = event.get("competitions") or []
        if not event_id or not competitions or not isinstance(competitions[0], dict):
            continue
        comp = competitions[0]

        sides: dict[str, Mapping[str, Any]] = {}
        for competitor in comp.get("competitors") or []:
            if not isinstance(competitor, dict):
                continue
            side = _clean(competitor.get("homeAway")).casefold()
            if side in {"home", "away"}:
                sides[side] = competitor
        if "home" not in sides or "away" not in sides:
            continue

        game_date = _espn_game_date(event.get("date") or comp.get("date"), requested_day)
        if game_date != requested_day:
            continue

        def team_info(side: str) -> tuple[str, str]:
            competitor = sides[side]
            team = competitor.get("team") if isinstance(competitor.get("team"), dict) else {}
            name = _clean(
                team.get("displayName")
                or team.get("shortDisplayName")
                or team.get("location")
                or team.get("name")
            )
            return name, _clean(team.get("id"))

        away_name, away_id = team_info("away")
        home_name, home_id = team_info("home")
        if not away_name or not home_name:
            continue

        status_type = (event.get("status") or {}).get("type") or {}
        broadcasts = comp.get("broadcasts") or []
        broadcast = ""
        if broadcasts and isinstance(broadcasts[0], dict):
            names = broadcasts[0].get("names") or []
            if isinstance(names, list):
                broadcast = ", ".join(_clean(v) for v in names if _clean(v))

        venue = comp.get("venue") if isinstance(comp.get("venue"), dict) else {}
        if event_id in seen_ids:
            continue
        seen_ids.add(event_id)
        games.append(
            {
                "event_id": event_id,
                "game_date": game_date,
                "away_team": away_name,
                "home_team": home_name,
                "away_team_id": away_id,
                "home_team_id": home_id,
                "venue": _clean(venue.get("fullName")),
                "broadcast": broadcast,
                "status": _clean(
                    status_type.get("description")
                    or status_type.get("detail")
                    or status_type.get("shortDetail")
                ),
                "sources": ["ESPN college-football scoreboard live identity fallback"],
            }
        )
    return games


def _fetch_espn_verified_games(
    requested_day: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # ESPN separates Division I football into group 80 (FBS) and group 81
    # (FCS). FanDuel's NCAAF board includes both, including cross-division
    # matchups, so query both exact-date surfaces and dedupe by ESPN event ID.
    combined: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for group_id, division in ((80, "FBS"), (81, "FCS")):
        params = {
            "dates": requested_day.replace("-", ""),
            "limit": 500,
            "groups": group_id,
        }
        try:
            response = httpx.get(
                ESPN_SCOREBOARD_URL,
                params=params,
                timeout=_HTTP_TIMEOUT,
                headers={
                    "User-Agent": "KyreSportsAPI/CFB-Odds-Step2",
                    "Accept": "application/json",
                },
            )
            status_code = int(response.status_code)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("ESPN scoreboard returned a non-object payload")
            games = _espn_verified_games_from_payload(payload, requested_day)
            combined.extend(games)
            attempts.append(
                {
                    "group_id": group_id,
                    "division": division,
                    "http": status_code,
                    "games": len(games),
                    "ok": True,
                }
            )
        except Exception as exc:
            attempts.append(
                {
                    "group_id": group_id,
                    "division": division,
                    "http": None,
                    "games": 0,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}"[:220],
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for game in combined:
        event_id = _clean(game.get("event_id"))
        if not event_id or event_id in seen:
            continue
        seen.add(event_id)
        deduped.append(game)

    ok = any(bool(row.get("ok")) for row in attempts)
    return deduped, {
        "date": requested_day,
        "source": "ESPN college-football scoreboard",
        "groups": attempts,
        "games": len(deduped),
        "ok": ok,
        "fail_closed": True,
    }


def _market_dates(feed: Mapping[str, Any]) -> list[str]:
    dates: set[str] = set()
    for row in feed.get("games") or []:
        if not isinstance(row, dict):
            continue
        try:
            dates.add(_parse_market_date(row.get("start_time_utc")))
        except ValueError:
            continue
    return sorted(dates)


def resolve_verified_games(
    feed: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    local_games, snapshot_diag = load_verified_games()
    market_dates = _market_dates(feed)

    combined = list(local_games)
    covered_dates = {
        str(game.get("game_date") or "")
        for game in combined
        if str(game.get("game_date") or "")
    }
    missing_dates = [day for day in market_dates if day not in covered_dates]

    github_diag: dict[str, Any] = {
        "source": "GitHub hourly CFB runtime snapshot",
        "attempted": False,
        "verified_games": 0,
    }
    if missing_dates:
        github_games, github_diag = _fetch_github_verified_games()
        github_diag = {**github_diag, "attempted": True}
        needed = set(missing_dates)
        combined.extend(
            game
            for game in github_games
            if str(game.get("game_date") or "") in needed
        )

    # A date being present is not enough: an FBS-only snapshot can contain the
    # date while still missing FCS games on the same slate. Supplement only dates
    # where at least one actual market row still has no deterministic identity
    # candidate. This keeps the direct ESPN fallback quiet when GitHub is complete.
    remaining_dates: list[str] = []
    for market in feed.get("games") or []:
        if not isinstance(market, Mapping):
            continue
        try:
            game_date, candidates = _qualified_candidates(market, combined)
        except ValueError:
            continue
        if not candidates and game_date not in remaining_dates:
            remaining_dates.append(game_date)
    remaining_dates.sort()

    provider_attempts: list[dict[str, Any]] = []
    for day in remaining_dates:
        fetched, diag = _fetch_espn_verified_games(day)
        provider_attempts.append(diag)
        combined.extend(fetched)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_ids = 0
    for game in combined:
        gid = _clean(game.get("event_id"))
        if not gid:
            continue
        if gid in seen:
            duplicate_ids += 1
            continue
        seen.add(gid)
        deduped.append(game)

    return deduped, {
        "resolver_mode": (
            "local verified snapshot + GitHub hourly verified snapshot + "
            "live ESPN FBS/FCS exact-date fallback"
        ),
        "requested_market_dates": market_dates,
        "snapshot": snapshot_diag,
        "github_snapshot": github_diag,
        "live_provider_attempts": provider_attempts,
        "verified_games": len(deduped),
        "duplicate_event_ids_ignored": duplicate_ids,
        "fail_closed": True,
    }


def _qualified_candidates(
    market: Mapping[str, Any],
    verified_games: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    game_date = _parse_market_date(market.get("start_time_utc"))
    candidates: list[dict[str, Any]] = []
    for verified in verified_games:
        if verified.get("game_date") != game_date:
            continue
        away_score = _name_score(market.get("away_team"), verified.get("away_team"))
        home_score = _name_score(market.get("home_team"), verified.get("home_team"))
        if away_score < MATCH_THRESHOLD or home_score < MATCH_THRESHOLD:
            continue
        pair_score = (away_score + home_score) / 2.0
        candidates.append(
            {
                "verified": verified,
                "away_score": away_score,
                "home_score": home_score,
                "pair_score": pair_score,
            }
        )
    candidates.sort(
        key=lambda row: (
            -float(row["pair_score"]),
            str(row["verified"].get("event_id") or ""),
        )
    )
    return game_date, candidates


def _attach_market(
    market: Mapping[str, Any],
    verified: Mapping[str, Any],
    *,
    game_date: str,
    away_score: float,
    home_score: float,
    pair_score: float,
) -> dict[str, Any]:
    return {
        "official_game_id": str(verified["event_id"]),
        "provider_game_id": _clean(market.get("game_id")),
        "game_date": game_date,
        "provider_away_team": _clean(market.get("away_team")),
        "provider_home_team": _clean(market.get("home_team")),
        "official_away_team": _clean(verified.get("away_team")),
        "official_home_team": _clean(verified.get("home_team")),
        "away_team_id": _clean(verified.get("away_team_id")),
        "home_team_id": _clean(verified.get("home_team_id")),
        "start_time_utc": _clean(market.get("start_time_utc")),
        "total": market.get("total"),
        "sportsbook": _clean(market.get("sportsbook")),
        "updated_at_utc": _clean(market.get("updated_at_utc")),
        "line_status": _clean(market.get("line_status")),
        "venue": _clean(verified.get("venue")),
        "broadcast": _clean(verified.get("broadcast")),
        "official_status": _clean(verified.get("status")),
        "identity_verified": True,
        "match_method": "eastern-date + deterministic away/home school identity",
        "match_confidence": round(float(pair_score), 6),
        "away_name_score": round(float(away_score), 6),
        "home_name_score": round(float(home_score), 6),
    }


def reconcile_market_feed(
    feed: Mapping[str, Any],
    verified_games: list[dict[str, Any]],
) -> dict[str, Any]:
    markets = feed.get("games")
    if not isinstance(markets, list):
        raise ValueError("market feed games must be a list")

    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for market in markets:
        if not isinstance(market, dict):
            unmatched.append(
                {
                    "provider_game_id": "",
                    "reason": "market_row_not_object",
                    "identity_verified": False,
                }
            )
            continue

        try:
            game_date, candidates = _qualified_candidates(market, verified_games)
        except ValueError as exc:
            unmatched.append(
                {
                    "provider_game_id": _clean(market.get("game_id")),
                    "provider_away_team": _clean(market.get("away_team")),
                    "provider_home_team": _clean(market.get("home_team")),
                    "reason": str(exc),
                    "identity_verified": False,
                }
            )
            continue

        if not candidates:
            unmatched.append(
                {
                    "provider_game_id": _clean(market.get("game_id")),
                    "game_date": game_date,
                    "provider_away_team": _clean(market.get("away_team")),
                    "provider_home_team": _clean(market.get("home_team")),
                    "sportsbook": _clean(market.get("sportsbook")),
                    "total": market.get("total"),
                    "reason": "no_verified_match",
                    "identity_verified": False,
                }
            )
            continue

        best = candidates[0]
        if (
            len(candidates) > 1
            and float(best["pair_score"]) - float(candidates[1]["pair_score"])
            < AMBIGUITY_MARGIN
        ):
            unmatched.append(
                {
                    "provider_game_id": _clean(market.get("game_id")),
                    "game_date": game_date,
                    "provider_away_team": _clean(market.get("away_team")),
                    "provider_home_team": _clean(market.get("home_team")),
                    "sportsbook": _clean(market.get("sportsbook")),
                    "total": market.get("total"),
                    "reason": "ambiguous_verified_match",
                    "candidate_official_game_ids": [
                        str(row["verified"].get("event_id") or "")
                        for row in candidates[:3]
                    ],
                    "identity_verified": False,
                }
            )
            continue

        matched.append(
            _attach_market(
                market,
                best["verified"],
                game_date=game_date,
                away_score=float(best["away_score"]),
                home_score=float(best["home_score"]),
                pair_score=float(best["pair_score"]),
            )
        )

    official_ids = {row["official_game_id"] for row in matched}
    provider_ids = {row["provider_game_id"] for row in matched if row["provider_game_id"]}
    semantics = dict(feed.get("market_semantics") or {})
    semantics.update(
        {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        }
    )
    return {
        "model_version": MODEL_VERSION,
        "schema_version": feed.get("schema_version"),
        "captured_at_utc": feed.get("captured_at_utc"),
        "source": feed.get("source"),
        "lines": matched,
        "unmatched": unmatched,
        "diagnostics": {
            "input_market_rows": len(markets),
            "matched_market_rows": len(matched),
            "unmatched_market_rows": len(unmatched),
            "unique_provider_games_matched": len(provider_ids),
            "unique_official_games_matched": len(official_ids),
            "all_lines_identity_verified": len(unmatched) == 0,
            "fail_closed": True,
            "synthetic_official_ids": False,
            "fuzzy_matching": False,
            "match_threshold": MATCH_THRESHOLD,
            "ambiguity_margin": AMBIGUITY_MARGIN,
        },
        "market_semantics": semantics,
    }


@router.get("/identity-status")
def identity_status():
    try:
        games, diag = load_verified_games()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "step": 2,
        "model_version": MODEL_VERSION,
        "identity_ready": True,
        "local_verified_games": len(games),
        "verified_snapshot": diag,
        "resolver_mode": (
            "local verified snapshot + GitHub hourly verified snapshot + "
            "live ESPN FBS/FCS exact-date fallback"
        ),
        "identity_policy": {
            "official_id_source": (
                "verified CFB runtime event_id; GitHub hourly snapshot event_id; "
                "ESPN scoreboard event_id final fallback"
            ),
            "fuzzy_matching": False,
            "synthetic_ids": False,
            "fail_closed": True,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


@router.get("/reconciled")
def reconciled(
    official_game_id: str | None = Query(default=None),
    provider_game_id: str | None = Query(default=None),
):
    feed = _load_feed()
    try:
        verified_games, resolver_diag = resolve_verified_games(feed)
        result = reconcile_market_feed(feed, verified_games)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    lines = result["lines"]
    if official_game_id is not None:
        lines = [
            row for row in lines
            if row["official_game_id"] == str(official_game_id).strip()
        ]
    if provider_game_id is not None:
        lines = [
            row for row in lines
            if row["provider_game_id"] == str(provider_game_id).strip()
        ]

    if (official_game_id is not None or provider_game_id is not None) and not lines:
        raise HTTPException(
            status_code=404,
            detail="No identity-verified CFB market line matched that game.",
        )

    output = dict(result)
    output["lines"] = lines
    output["identity_resolution"] = resolver_diag
    if official_game_id is not None or provider_game_id is not None:
        output["unmatched"] = []
        output["diagnostics"] = dict(result["diagnostics"])
        output["diagnostics"]["filtered_line_count"] = len(lines)
    return output


__all__ = [
    "AMBIGUITY_MARGIN",
    "DEFAULT_GITHUB_VERIFIED_SNAPSHOT_URL",
    "ESPN_SCOREBOARD_URL",
    "GITHUB_VERIFIED_SNAPSHOT_URL_ENV",
    "MATCH_THRESHOLD",
    "MODEL_VERSION",
    "SNAPSHOT_PATH_ENV",
    "_espn_verified_games_from_payload",
    "_fetch_github_verified_games",
    "_github_verified_games_from_payload",
    "_name_score",
    "load_verified_games",
    "reconcile_market_feed",
    "resolve_verified_games",
    "router",
]
