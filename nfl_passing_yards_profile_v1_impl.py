"""NFL Passing Yards Step 2 — descriptive quarterback passing profile.

Primary source: ESPN NFL athlete season statistics.
Secondary/recent source: ESPN NFL athlete game log.

Early-season rule: current regular-season data always wins. If the selected
regular season has no usable completed-game baseline yet, the immediately prior
regular season is allowed as a clearly-labelled fallback. Recent rolling history
may be filled from that prior season so downstream variance does not disappear
on opening weekend. No sportsbook input is used and nothing is synthesized.
"""
from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd
import requests
import streamlit as st

import nfl_passing_yards_early_season_v1 as early

MODEL_VERSION = "NFL PASSING YARDS STEP 2 • QB PASSING PROFILE V1"
CORE_BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
GAMELOG_BASE = "https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
    "Accept": "application/json,text/plain,*/*",
}


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _json_get(url: str, timeout: int = 8):
    diag = {"url": url, "http": None, "ok": False, "error": ""}
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        diag["http"] = int(r.status_code)
        r.raise_for_status()
        payload = r.json()
        diag["ok"] = True
        return payload, diag
    except Exception as exc:
        diag["error"] = str(exc)[:220]
        return {}, diag


@st.cache_data(ttl=300, show_spinner=False)
def _season_stats_payload(year: int, season_type: int, athlete_id: str):
    athlete_id = _safe(athlete_id)
    if not athlete_id:
        return {}, {"ok": False, "http": None, "error": "missing athlete id"}
    url = f"{CORE_BASE}/seasons/{int(year)}/types/{int(season_type)}/athletes/{athlete_id}/statistics"
    return _json_get(url)


@st.cache_data(ttl=300, show_spinner=False)
def _gamelog_payload(year: int, athlete_id: str):
    athlete_id = _safe(athlete_id)
    if not athlete_id:
        return {}, {"ok": False, "http": None, "error": "missing athlete id"}
    url = f"{GAMELOG_BASE}/{athlete_id}/gamelog?season={int(year)}"
    return _json_get(url)


def _norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _safe(text).lower())


def _passing_category(payload: dict):
    splits = (payload or {}).get("splits") or {}
    cats = splits.get("categories") if isinstance(splits, dict) else None
    candidates = cats if isinstance(cats, list) else []
    if not candidates:
        candidates = (payload or {}).get("categories") or []
    for cat in candidates:
        if not isinstance(cat, dict):
            continue
        name = _norm(cat.get("name") or cat.get("displayName") or cat.get("abbreviation"))
        if "passing" in name or name in {"pass", "passstats"}:
            return cat
    return {}


def _stat_map(payload: dict) -> dict:
    cat = _passing_category(payload)
    stats = cat.get("stats") or [] if isinstance(cat, dict) else []
    out = {}
    for item in stats:
        if not isinstance(item, dict):
            continue
        keys = {
            _norm(item.get("name")),
            _norm(item.get("displayName")),
            _norm(item.get("abbreviation")),
            _norm(item.get("shortDisplayName")),
        }
        value = item.get("value")
        if not _finite(value):
            value = item.get("displayValue")
        for key in keys:
            if key:
                out[key] = _num(value)
    return out


def _pick(stats: dict, aliases: tuple[str, ...]):
    for alias in aliases:
        key = _norm(alias)
        if key in stats and _finite(stats[key]):
            return float(stats[key])
    return math.nan


def parse_season_passing(payload: dict) -> dict:
    stats = _stat_map(payload)
    games = _pick(stats, ("gamesPlayed", "games", "GP"))
    completions = _pick(stats, ("completions", "CMP"))
    attempts = _pick(stats, ("passingAttempts", "passAttempts", "attempts", "ATT"))
    yards = _pick(stats, ("passingYards", "passYards", "YDS"))
    touchdowns = _pick(stats, ("passingTouchdowns", "passTouchdowns", "TD"))
    interceptions = _pick(stats, ("interceptions", "passingInterceptions", "INT"))
    comp_pct = _pick(stats, ("completionPct", "completionPercentage", "completionPercent", "CMP%"))
    ypa = _pick(stats, ("yardsPerPassAttempt", "yardsPerAttempt", "Y/A", "AVG"))

    if not _finite(comp_pct) and _finite(completions) and _finite(attempts) and attempts > 0:
        comp_pct = 100.0 * completions / attempts
    if not _finite(ypa) and _finite(yards) and _finite(attempts) and attempts > 0:
        ypa = yards / attempts
    ypg = yards / games if _finite(yards) and _finite(games) and games > 0 else math.nan
    att_pg = attempts / games if _finite(attempts) and _finite(games) and games > 0 else math.nan
    cmp_pg = completions / games if _finite(completions) and _finite(games) and games > 0 else math.nan

    ready = all(_finite(x) for x in (games, completions, attempts, yards)) and games > 0 and attempts > 0
    return {
        "ready": bool(ready),
        "games": games,
        "completions": completions,
        "attempts": attempts,
        "passing_yards": yards,
        "passing_tds": touchdowns,
        "interceptions": interceptions,
        "completion_pct": comp_pct,
        "yards_per_attempt": ypa,
        "yards_per_game": ypg,
        "attempts_per_game": att_pg,
        "completions_per_game": cmp_pg,
    }


def _gamelog_category(payload: dict):
    # Older ESPN payloads put labels/events directly on the passing category.
    for cat in (payload or {}).get("categories", []) or []:
        if not isinstance(cat, dict):
            continue
        name = _norm(cat.get("name") or cat.get("displayName"))
        if "passing" in name or name == "pass":
            return cat
    return {}


def _event_meta_map(payload: dict) -> dict:
    raw = (payload or {}).get("events") or {}
    # Current common/v3 gamelog payloads can expose event metadata as a map.
    if isinstance(raw, dict):
        if isinstance(raw.get("items"), list):
            raw = raw.get("items")
        else:
            return raw
    out = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                event = item.get("event") if isinstance(item.get("event"), dict) else item
                key = _safe(event.get("id") or item.get("id") or item.get("eventId"))
                if key:
                    merged = dict(event)
                    merged.update({k: v for k, v in item.items() if k not in merged})
                    out[key] = merged
    return out


def _top_level_gamelog_rows(payload: dict, category_name: str = "passing") -> tuple[list[str], list[dict]]:
    """Handle current ESPN common/v3 shape where categories are metadata only."""
    labels: list[str] = []
    rows: list[dict] = []
    # Some versions expose names/labels once at the payload root.
    for key in ("labels", "names", "displayNames"):
        raw = (payload or {}).get(key)
        if isinstance(raw, list) and raw:
            labels = [_safe(x) for x in raw]
            break
    raw_events = (payload or {}).get("events")
    if isinstance(raw_events, dict) and isinstance(raw_events.get("items"), list):
        raw_events = raw_events.get("items")
    if isinstance(raw_events, list):
        for item in raw_events:
            if not isinstance(item, dict):
                continue
            category = _norm(item.get("category") or item.get("name") or item.get("type"))
            if category and category_name not in category:
                continue
            if item.get("stats") is not None or item.get("statistics") is not None:
                rows.append(dict(item))
    return labels, rows


def parse_recent_passing(payload: dict) -> list[dict]:
    cat = _gamelog_category(payload)
    labels = [_safe(x) for x in (cat.get("labels") or [])]
    norm_labels = [_norm(x) for x in labels]
    events = cat.get("events") or []

    if not events:
        top_labels, top_rows = _top_level_gamelog_rows(payload)
        if top_rows:
            labels = top_labels or labels
            norm_labels = [_norm(x) for x in labels]
            events = top_rows

    if isinstance(events, dict):
        iterable = []
        event_items = events.get("items") if isinstance(events.get("items"), list) else None
        if event_items is not None:
            iterable = [dict(x) for x in event_items if isinstance(x, dict)]
        else:
            for key, value in events.items():
                if isinstance(value, dict):
                    row = dict(value)
                    row.setdefault("eventId", key)
                    iterable.append(row)
    else:
        iterable = list(events) if isinstance(events, list) else []

    meta_map = _event_meta_map(payload)
    out = []
    for item in iterable:
        if not isinstance(item, dict):
            continue
        raw_stats = item.get("stats") or item.get("statistics") or []
        if isinstance(raw_stats, dict):
            stat_lookup = {_norm(k): _num(v) for k, v in raw_stats.items()}
        else:
            vals = list(raw_stats) if isinstance(raw_stats, list) else []
            stat_lookup = {norm_labels[i]: _num(vals[i]) for i in range(min(len(norm_labels), len(vals)))}

        def pick(*aliases):
            for alias in aliases:
                key = _norm(alias)
                if key in stat_lookup and _finite(stat_lookup[key]):
                    return float(stat_lookup[key])
            return math.nan

        event_obj = item.get("event") if isinstance(item.get("event"), dict) else {}
        event_id = _safe(item.get("eventId") or item.get("id") or event_obj.get("id"))
        meta = meta_map.get(event_id) or event_obj or {}
        opponent = meta.get("opponent") or item.get("opponent") or {}
        opponent_name = _safe(
            opponent.get("abbreviation") if isinstance(opponent, dict) else opponent,
            _safe(meta.get("opponentName") or item.get("opponentName"), "—"),
        )
        date_value = meta.get("date") or item.get("date") or item.get("gameDate")
        try:
            date_text = pd.to_datetime(date_value).strftime("%Y-%m-%d") if date_value else ""
        except Exception:
            date_text = _safe(date_value)
        site = _safe(meta.get("atVs") or item.get("atVs") or meta.get("homeAway") or item.get("homeAway"))
        home_away = "away" if site.lower() in {"@", "away"} else ("home" if site.lower() in {"vs", "home"} else "")
        row = {
            "event_id": event_id,
            "date": date_text,
            "opponent": opponent_name,
            "home_away": home_away,
            "completions": pick("CMP", "completions"),
            "attempts": pick("ATT", "passingAttempts", "attempts"),
            "passing_yards": pick("YDS", "passingYards", "yards"),
            "passing_tds": pick("TD", "passingTouchdowns"),
            "interceptions": pick("INT", "interceptions"),
        }
        if _finite(row["passing_yards"]) and _finite(row["attempts"]):
            out.append(row)

    def sort_key(row):
        try:
            return pd.to_datetime(row.get("date"), errors="coerce")
        except Exception:
            return pd.NaT

    out.sort(key=lambda r: sort_key(r) if pd.notna(sort_key(r)) else pd.Timestamp.min, reverse=True)
    return out


def _avg(rows: list[dict], key: str):
    values = [_num(r.get(key)) for r in rows]
    values = [x for x in values if _finite(x)]
    return sum(values) / len(values) if values else math.nan


def build_qb_profile(athlete_id: str, qb_name: str, year: int, season_type: int = 2) -> dict:
    athlete_id = _safe(athlete_id)
    qb_name = _safe(qb_name, "Unknown QB")
    if not athlete_id:
        return {"ready": False, "reason": "missing verified athlete ID", "athlete_id": "", "qb_name": qb_name}

    year = int(year)
    season_type = int(season_type)
    season_payload, season_diag = _season_stats_payload(year, season_type, athlete_id)
    current_season = parse_season_passing(season_payload) if season_diag.get("ok") else {"ready": False}
    season = current_season
    source_year = year
    fallback_used = False
    fallback_season_diag = {"http": None, "ok": False}

    if not current_season.get("ready") and early.allow_prior_regular_fallback(season_type):
        prior_year = early.prior_regular_year(year)
        prior_payload, fallback_season_diag = _season_stats_payload(prior_year, 2, athlete_id)
        prior_season = parse_season_passing(prior_payload) if fallback_season_diag.get("ok") else {"ready": False}
        if prior_season.get("ready"):
            season = prior_season
            source_year = prior_year
            fallback_used = True

    gamelog_payload, gamelog_diag = _gamelog_payload(year, athlete_id)
    current_games = parse_recent_passing(gamelog_payload) if gamelog_diag.get("ok") else []
    prior_games: list[dict] = []
    prior_gamelog_diag = {"http": None, "ok": False}
    if len(current_games) < 5 and early.allow_prior_regular_fallback(season_type):
        prior_year = early.prior_regular_year(year)
        prior_payload, prior_gamelog_diag = _gamelog_payload(prior_year, athlete_id)
        if prior_gamelog_diag.get("ok"):
            prior_games = parse_recent_passing(prior_payload)

    games = early.merge_recent_rows(current_games, prior_games, limit=5)
    recent3 = games[:3]
    recent5 = games[:5]
    home = [x for x in games if x.get("home_away") == "home"]
    away = [x for x in games if x.get("home_away") == "away"]
    prov = early.provenance(bool(current_season.get("ready")), fallback_used, year, source_year)
    result = {
        "ready": bool(season.get("ready")),
        "reason": "" if season.get("ready") else "verified season passing totals are incomplete",
        "athlete_id": athlete_id,
        "qb_name": qb_name,
        "season_year": source_year,
        "requested_season_year": year,
        "season_type": season_type,
        "season": season,
        "recent_games": games,
        "current_recent_games": len(current_games),
        "prior_recent_games_used": max(0, len(games) - len(current_games[:5])),
        "recent3_yards": _avg(recent3, "passing_yards"),
        "recent3_attempts": _avg(recent3, "attempts"),
        "recent5_yards": _avg(recent5, "passing_yards"),
        "recent5_attempts": _avg(recent5, "attempts"),
        "home_yards": _avg(home, "passing_yards"),
        "away_yards": _avg(away, "passing_yards"),
        "home_games": len(home),
        "away_games": len(away),
        "season_http": season_diag.get("http"),
        "fallback_season_http": fallback_season_diag.get("http"),
        "gamelog_http": gamelog_diag.get("http"),
        "fallback_gamelog_http": prior_gamelog_diag.get("http"),
        "season_source_ok": bool(season_diag.get("ok") or fallback_season_diag.get("ok")),
        "gamelog_source_ok": bool(gamelog_diag.get("ok") or prior_gamelog_diag.get("ok")),
        **prov,
    }
    return result


__all__ = [
    "MODEL_VERSION",
    "build_qb_profile",
    "parse_recent_passing",
    "parse_season_passing",
]
