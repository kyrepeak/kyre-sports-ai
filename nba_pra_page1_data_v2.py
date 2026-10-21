"""NBA PRA Page 1 V2 live-market routing overlay.

Preserves the frozen/current Page-1 snapshot implementation in
``nba_pra_page1_data_core_v2`` while fixing sportsbook credential reuse,
Phoenix-local market windows, and primary-to-secondary routing.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any, Mapping

import nba_pra_page1_data_core_v2 as _core
import nba_pra_page1_sgo_v1 as _sgo
from nba_pra_page1_common_v1 import PHOENIX_TZ
from nba_pra_page1_sources_v2 import load_approved_odds_api_pra_observations
from nba_pra_market_api_v1 import load_kyre_sports_api_pra_observations

_NBA_TEAM_NAME_BY_TRICODE = {
    "ATL":"Atlanta Hawks","BOS":"Boston Celtics","BKN":"Brooklyn Nets","CHA":"Charlotte Hornets",
    "CHI":"Chicago Bulls","CLE":"Cleveland Cavaliers","DAL":"Dallas Mavericks","DEN":"Denver Nuggets",
    "DET":"Detroit Pistons","GSW":"Golden State Warriors","HOU":"Houston Rockets","IND":"Indiana Pacers",
    "LAC":"LA Clippers","LAL":"Los Angeles Lakers","MEM":"Memphis Grizzlies","MIA":"Miami Heat",
    "MIL":"Milwaukee Bucks","MIN":"Minnesota Timberwolves","NOP":"New Orleans Pelicans","NYK":"New York Knicks",
    "OKC":"Oklahoma City Thunder","ORL":"Orlando Magic","PHI":"Philadelphia 76ers","PHX":"Phoenix Suns",
    "POR":"Portland Trail Blazers","SAC":"Sacramento Kings","SAS":"San Antonio Spurs","TOR":"Toronto Raptors",
    "UTA":"Utah Jazz","WAS":"Washington Wizards",
}

# Preserve the existing module surface, including private helpers used by tests.
globals().update({k: v for k, v in vars(_core).items() if not k.startswith("__")})


def _connected_secret(name: str) -> str | None:
    session_key = {
        "SPORTSGAMEODDS_API_KEY": "ks_sportsgameodds_key",
        "SGO_API_KEY": "ks_sportsgameodds_key",
        "ODDS_API_IO_KEY": "ks_odds_api_key",
        "ODDS_API_KEY": "ks_odds_api_key",
    }.get(str(name or "").strip())
    secret_names = [str(name or "").strip()]
    if secret_names[0] in {"SPORTSGAMEODDS_API_KEY", "SGO_API_KEY"}:
        secret_names.append("SPORTSGAMEODDS_KEY")
    try:
        import streamlit as st
        if session_key:
            value = st.session_state.get(session_key)
            if value:
                return str(value).strip() or None
        for secret_name in secret_names:
            value = st.secrets.get(secret_name)
            if value:
                return str(value).strip() or None
    except Exception:
        pass
    import os
    for secret_name in secret_names:
        value = os.getenv(secret_name)
        if value:
            return str(value).strip() or None
    return None


def _phoenix_window(slate_date):
    start = datetime.combine(slate_date, time.min, tzinfo=PHOENIX_TZ)
    end = start + timedelta(days=1)
    fmt = lambda value: value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return fmt(start), fmt(end)


_FANDUEL_SCHEDULE_URL = "https://api.sportsbook.fanduel.com/sbapi/content-managed-page"
_FANDUEL_PUBLIC_WEB_KEY = "FhMFpcPWXMeyZxOx"


def _mapping_rows(value):
    if isinstance(value, Mapping):
        return [row for row in value.values() if isinstance(row, Mapping)]
    if isinstance(value, list):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def _team_code_from_name(value: Any) -> str | None:
    token = "".join(ch for ch in str(value or "").casefold() if ch.isalnum())
    aliases = {
        "losangelesclippers": "LAC",
        "laclippers": "LAC",
        "portlandtrailblazers": "POR",
    }
    if token in aliases:
        return aliases[token]
    for code, name in _NBA_TEAM_NAME_BY_TRICODE.items():
        if token == "".join(ch for ch in name.casefold() if ch.isalnum()):
            return code
    return None


def _recover_quorum_schedule(
    schedule: Mapping[str, Any],
    now_utc: datetime,
    *,
    request_get=None,
    timeout: float = 6.0,
) -> dict[str, Any]:
    result = dict(schedule or {})
    if result.get("games") or result.get("diagnostic_state") != "PROVIDER_CONFLICT":
        return result
    provider_keys = result.get("provider_game_keys") or {}
    if not isinstance(provider_keys, Mapping):
        return result
    official = set(provider_keys.get("NBA Official") or [])
    espn = set(provider_keys.get("ESPN NBA") or [])
    conflict = set(result.get("conflict_game_keys") or [])
    confirmed = (official & espn) - conflict
    if not confirmed:
        return result

    upstream = request_get or _sgo._default_get
    try:
        response = upstream(
            _FANDUEL_SCHEDULE_URL,
            params={
                "_ak": _FANDUEL_PUBLIC_WEB_KEY,
                "page": "CUSTOM",
                "customPageId": "nba",
                "timezone": "America/Phoenix",
            },
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
                "Origin": "https://sportsbook.fanduel.com",
                "Referer": "https://sportsbook.fanduel.com/",
                "x-sportsbook-region": "NJ",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        document = response.json()
    except Exception as exc:
        return {**result, "schedule_recovery_state": f"FANDUEL_ERROR:{type(exc).__name__}"}

    attachments = document.get("attachments") if isinstance(document, Mapping) else None
    if not isinstance(attachments, Mapping):
        return {**result, "schedule_recovery_state": "FANDUEL_NO_ATTACHMENTS"}
    nba_competitions = {
        str(row.get("competitionId") or row.get("id") or "").strip()
        for row in _mapping_rows(attachments.get("competitions"))
        if str(row.get("name") or row.get("competitionName") or "").strip().casefold() == "nba"
    }
    now = now_utc if now_utc.tzinfo is not None else now_utc.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    recovered = []
    for event in _mapping_rows(attachments.get("events")):
        if nba_competitions and str(event.get("competitionId") or "").strip() not in nba_competitions:
            continue
        name = str(event.get("name") or event.get("eventName") or "").strip()
        if " @ " not in name:
            continue
        away_name, home_name = (part.strip() for part in name.split(" @ ", 1))
        away_code, home_code = _team_code_from_name(away_name), _team_code_from_name(home_name)
        if not away_code or not home_code:
            continue
        raw_tip = str(event.get("openDate") or event.get("startTime") or "").strip()
        try:
            tip = datetime.fromisoformat(raw_tip.replace("Z", "+00:00"))
        except ValueError:
            continue
        if tip.tzinfo is None:
            tip = tip.replace(tzinfo=timezone.utc)
        tip = tip.astimezone(timezone.utc)
        if tip <= now:
            continue
        phoenix_day = tip.astimezone(PHOENIX_TZ).date().isoformat()
        game_key = f"{away_code}@{home_code}:{phoenix_day}"
        if game_key not in confirmed:
            continue
        recovered.append({
            "game_key": game_key,
            "source_game_id": str(event.get("eventId") or event.get("id") or ""),
            "away_tricode": away_code,
            "home_tricode": home_code,
            "away_name": _NBA_TEAM_NAME_BY_TRICODE[away_code],
            "home_name": _NBA_TEAM_NAME_BY_TRICODE[home_code],
            "status": "UPCOMING",
            "gameStatus": 1,
            "tip_utc": tip.isoformat().replace("+00:00", "Z"),
            "game_date_phoenix": phoenix_day,
            "confirming_sources": ["NBA Official", "ESPN NBA", "FanDuel schedule recovery"],
            "source_agreement": 2,
        })
    if not recovered:
        return {**result, "schedule_recovery_state": "FANDUEL_NO_CONFIRMED_FUTURE_GAMES"}
    recovered.sort(key=lambda game: (game["tip_utc"], game["game_key"]))
    return {
        **result,
        "verification": "VERIFIED",
        "diagnostic_state": "QUORUM_RECOVERED_AFTER_ISOLATED_CONFLICT",
        "games": recovered,
        "source_agreement": 2,
        "schedule_recovery_state": "RECOVERED",
    }


def _load_sgo_primary(slate_date, *, request_get=None, secret_getter=None, timeout: float = 6.0):
    upstream = request_get or _sgo._default_get
    starts_after, starts_before = _phoenix_window(slate_date)

    def phoenix_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        params["startsAfter"] = starts_after
        params["startsBefore"] = starts_before
        kwargs["params"] = params
        return upstream(url, **kwargs)

    return _sgo.load_sgo_pra_observations(
        slate_date,
        request_get=phoenix_get,
        secret_getter=secret_getter or _connected_secret,
        timeout=timeout,
    )


def _load_odds_secondary(slate_date):
    return load_approved_odds_api_pra_observations(slate_date, secret_getter=_connected_secret)


def _team_tokens(game: Mapping[str, Any], side: str) -> tuple[str, ...]:
    values = []
    for key in (f"{side}_name", f"{side}_team", f"{side}_full_name", f"{side}_tricode"):
        raw = str(game.get(key) or "").strip()
        token = "".join(ch for ch in raw.casefold() if ch.isalnum())
        if token:
            values.append(token)
        if key.endswith("_tricode") and raw.upper() in _NBA_TEAM_NAME_BY_TRICODE:
            full = _NBA_TEAM_NAME_BY_TRICODE[raw.upper()]
            values.append("".join(ch for ch in full.casefold() if ch.isalnum()))
    return tuple(dict.fromkeys(values))


def _team_matches(observed: Any, candidates: tuple[str, ...]) -> bool:
    token = "".join(ch for ch in str(observed or "").casefold() if ch.isalnum())
    if not token:
        return False
    for candidate in candidates:
        if token == candidate:
            return True
        # Allow full-name vs short-name variants, but never use tiny tokens as
        # fuzzy matches (e.g. a 3-letter tricode alone cannot match a full name).
        if len(candidate) >= 5 and (token.endswith(candidate) or candidate.endswith(token)):
            return True
    return False


def _row_matches_game(row: Mapping[str, Any], game: Mapping[str, Any]) -> bool:
    return _team_matches(row.get("away_team"), _team_tokens(game, "away")) and _team_matches(
        row.get("home_team"), _team_tokens(game, "home")
    )


def _filter_payload_to_games(payload: Mapping[str, Any], games) -> dict[str, Any]:
    out = dict(payload or {})
    rows = [row for row in (out.get("observations") or []) if isinstance(row, Mapping)]
    filtered = [dict(row) for row in rows if any(_row_matches_game(row, game) for game in games)]
    out["observations"] = filtered
    out["upcoming_match_observation_count"] = len(filtered)
    return out


def _primary_market_covers_games(payload: Mapping[str, Any], games) -> bool:
    rows = [row for row in (payload.get("observations") or []) if isinstance(row, Mapping)]
    if not rows or not games:
        return False
    return all(any(_row_matches_game(row, game) for row in rows) for game in games)

def _skipped_secondary():
    return {
        "source": "Odds-API.io",
        "verification": "SKIPPED_PRIMARY_COMPLETE",
        "diagnostic_state": "SKIPPED_PRIMARY_COMPLETE",
        "observations": [],
        "fabrication": False,
        "sportsbook_projection_influence": 0.0,
    }


def load_page1_snapshot_v2(
    *, now=None, schedule_loader=None, api_loader=None, sgo_loader=None, odds_loader=None,
    official_profile_loader=None, backup_profile_loader=None, injury_loader=None,
    schedule_recovery_get=None,
):
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    schedule_impl = schedule_loader or _core._default_schedule_loader
    api_impl = api_loader or (lambda day: load_kyre_sports_api_pra_observations(day, api_key=_connected_secret("SPORTSGAMEODDS_API_KEY")))
    primary_impl = sgo_loader or _load_sgo_primary
    secondary_impl = odds_loader or _load_odds_secondary
    state = {}

    def schedule_proxy(**kwargs):
        result = dict(schedule_impl(**kwargs) or {})
        result = _recover_quorum_schedule(
            result, now_utc, request_get=schedule_recovery_get
        )
        _, games = _core.select_next_upcoming_slate(list(result.get("games") or []), now_utc)
        state["games"] = games
        return result

    def primary_proxy(day):
        api_result = _filter_payload_to_games(dict(api_impl(day) or {}), state.get("games", []))
        state["api"] = api_result
        if _primary_market_covers_games(api_result, state.get("games", [])):
            state["primary"] = api_result
            state["api_complete"] = True
            return api_result
        # If the API is alive but partial, do not repeat its primary provider call;
        # preserve those rows and let the approved secondary fill missing coverage.
        if api_result.get("verification") == "VERIFIED" and api_result.get("observations"):
            state["primary"] = api_result
            state["api_partial"] = True
            return api_result
        direct = _filter_payload_to_games(dict(primary_impl(day) or {}), state.get("games", []))
        state["primary"] = direct
        return direct

    def secondary_proxy(day):
        if _primary_market_covers_games(state.get("primary", {}), state.get("games", [])):
            return _skipped_secondary()
        return _filter_payload_to_games(dict(secondary_impl(day) or {}), state.get("games", []))

    result = _core.load_page1_snapshot_v2(
        now=now_utc,
        schedule_loader=schedule_proxy,
        sgo_loader=primary_proxy,
        odds_loader=secondary_proxy,
        official_profile_loader=official_profile_loader,
        backup_profile_loader=backup_profile_loader,
        injury_loader=injury_loader,
    )
    sources = dict(result.get("sources") or {})
    sources["kyre_sports_api"] = state.get("api") or {}
    result["sources"] = sources
    return result
