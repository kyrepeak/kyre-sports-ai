"""CFB Over/Under post-12 multi-source data recovery hotfix.

Purpose
-------
The permanently frozen 12-step stack is preserved exactly. This module repairs
data availability ABOVE that stack when one provider path fails.

Recovery hierarchy
------------------
Environment / identity:
1. Frozen Step-9 exact-date ESPN scoreboard resolver.
2. Existing ESPN visual/team-id resolver.
3. ESPN college-football team directory.
4. Exact ESPN team-schedule pair/date lookup for the event id.
5. ESPN event summary / roster endpoints once the event is recovered.

Historical matchup context:
1. Frozen Step-10 ESPN team schedules.
2. Winsipedia game-by-game head-to-head fallback for all-time series context.

Rules
-----
- Exact team IDs are required before a recovered ESPN event can affect weather.
- Team-schedule event matching requires the exact two ESPN IDs and target date
  proximity; no name-only event guess is allowed.
- Winsipedia H2H is context/audit data only and has 0% projection/selection
  weight.
- No sportsbook, market probability, EV, price, or Monte Carlo is added.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re
from statistics import fmean, pstdev
from typing import Any, Mapping

import requests
import streamlit as st

import cfb_over_under_environment_engine_v1 as frozen_environment
import cfb_over_under_history_engine_v1 as frozen_history
import cfb_over_under_logo_resolver_v1 as logo_identity

_FROZEN_ENV_BUILD = frozen_environment.build_environment_engine
_FROZEN_HISTORY_BUILD = frozen_history.build_history_engine

MODEL_VERSION = "CFB O/U MULTI-SOURCE DATA RECOVERY V1 • POST-12 HOTFIX"
FROZEN_STEP12_COMPLETE = True

ESPN_TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams"
)
WINSIPEDIA_BASE = "https://www.winsipedia.com"

EXTERNAL_HISTORY_PROJECTION_WEIGHT = 0.0
EXTERNAL_HISTORY_SELECTION_WEIGHT = 0.0
EXTERNAL_HISTORY_ANALYSIS_LINE_WEIGHT = 0.0

# Stable ESPN IDs for a few ambiguous names where the public directory's
# location string can be insufficient by itself.
_ESPN_ID_OVERRIDES = {
    "miamifl": "2390",
    "miamiflorida": "2390",
    "miamioh": "193",
    "miamiohio": "193",
    "floridaam": "50",
}

_WINSIPEDIA_SLUG_OVERRIDES = {
    "miamifl": "miami-fl",
    "miamiflorida": "miami-fl",
    "miamioh": "miami-oh",
    "miamiohio": "miami-oh",
    "floridaam": "florida-am",
    "ncstate": "north-carolina-state",
    "northcarolinastate": "north-carolina-state",
    "olemiss": "ole-miss",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _key(value: Any) -> str:
    text = _clean(value).lower()
    text = text.replace("&", " and ")
    text = text.replace("(fl)", " florida ")
    text = text.replace("(oh)", " ohio ")
    text = re.sub(r"\bthe\b", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _target_dt(game: Mapping[str, Any]) -> datetime | None:
    return _parse_dt(game.get("kickoff_iso") or game.get("date"))


def _season(game: Mapping[str, Any]) -> int:
    try:
        return int(_clean(game.get("game_date"))[:4])
    except Exception:
        return datetime.now(timezone.utc).year


def _team_query_names(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "away": _clean(
            game.get("away_team")
            or away.get("team")
            or away.get("name")
        ),
        "home": _clean(
            game.get("home_team")
            or home.get("team")
            or home.get("name")
        ),
    }


@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_espn_teams() -> dict[str, Any]:
    try:
        response = requests.get(
            ESPN_TEAMS_URL,
            params={"limit": 1000},
            timeout=10,
            headers={"User-Agent": "KyreSportsAI/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _iter_team_objects(payload: Mapping[str, Any]):
    stack: list[Any] = [payload]
    seen_ids: set[int] = set()
    while stack:
        current = stack.pop()
        if id(current) in seen_ids:
            continue
        seen_ids.add(id(current))
        if isinstance(current, Mapping):
            team = current.get("team")
            if isinstance(team, Mapping) and _clean(team.get("id")):
                yield team
            for value in current.values():
                if isinstance(value, (Mapping, list)):
                    stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)


def _team_fields(team: Mapping[str, Any]) -> list[str]:
    return [
        _clean(team.get("displayName")),
        _clean(team.get("shortDisplayName")),
        _clean(team.get("location")),
        _clean(team.get("name")),
        _clean(team.get("abbreviation")),
        _clean(team.get("slug")),
    ]


def _resolve_team_id_from_directory(name: str) -> str:
    wanted = _key(name)
    if not wanted:
        return ""
    if wanted in _ESPN_ID_OVERRIDES:
        return _ESPN_ID_OVERRIDES[wanted]

    payload = _fetch_espn_teams()
    candidates: list[tuple[int, str]] = []
    for team in _iter_team_objects(payload):
        team_id = _clean(team.get("id"))
        if not team_id.isdigit():
            continue
        keys = {_key(v) for v in _team_fields(team) if _clean(v)}
        keys.discard("")
        score = 0
        if wanted in keys:
            score = 100
        else:
            aliases = logo_identity._aliases(name)
            candidate_aliases: set[str] = set()
            for field in _team_fields(team):
                candidate_aliases |= logo_identity._aliases(field)
            if logo_identity._overlap(aliases, candidate_aliases):
                score = 40
            if wanted and any(
                len(wanted) >= 6 and (wanted in k or k in wanted)
                for k in keys
                if len(k) >= 6
            ):
                score = max(score, 60)
        if score:
            candidates.append((score, team_id))

    if not candidates:
        return ""
    candidates.sort(reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return ""
    return candidates[0][1]


def resolve_espn_team_ids(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    base_environment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = dict(base_environment or {})
    away_id = _clean(base.get("away_espn_team_id"))
    home_id = _clean(base.get("home_espn_team_id"))
    source = "Step 9 exact-event"

    if not (away_id.isdigit() and home_id.isdigit()):
        try:
            visuals = logo_identity.resolve_visuals(game)
        except Exception:
            visuals = {}
        va = _clean((visuals.get("away") or {}).get("team_id"))
        vh = _clean((visuals.get("home") or {}).get("team_id"))
        if va.isdigit() and vh.isdigit():
            away_id, home_id = va, vh
            source = "ESPN visual resolver"

    names = _team_query_names(game, away, home)
    if not away_id.isdigit():
        away_id = _resolve_team_id_from_directory(names["away"])
        if away_id:
            source = "ESPN team directory"
    if not home_id.isdigit():
        home_id = _resolve_team_id_from_directory(names["home"])
        if home_id:
            source = "ESPN team directory"

    return {
        "ready": bool(away_id.isdigit() and home_id.isdigit()),
        "away_team_id": away_id,
        "home_team_id": home_id,
        "source": source if away_id and home_id else "unresolved",
        "away_name": names["away"],
        "home_name": names["home"],
    }


def _competition(event: Mapping[str, Any]) -> Mapping[str, Any]:
    comps = event.get("competitions") or []
    if comps and isinstance(comps[0], Mapping):
        return comps[0]
    return {}


def _event_team_ids(event: Mapping[str, Any]) -> set[str]:
    comp = _competition(event)
    out = set()
    for competitor in comp.get("competitors") or []:
        if not isinstance(competitor, Mapping):
            continue
        team = competitor.get("team") or {}
        if isinstance(team, Mapping):
            team_id = _clean(team.get("id"))
            if team_id:
                out.add(team_id)
    return out


def _event_date_distance_hours(
    event: Mapping[str, Any],
    target: datetime | None,
) -> float:
    if target is None:
        return 0.0
    dt = _parse_dt(event.get("date") or _competition(event).get("date"))
    if dt is None:
        return 1e9
    return abs((dt - target).total_seconds()) / 3600.0


def _find_event_from_team_schedules(
    game: Mapping[str, Any],
    away_id: str,
    home_id: str,
) -> dict[str, Any]:
    if not (away_id.isdigit() and home_id.isdigit()):
        return {}
    year = _season(game)
    target = _target_dt(game)
    wanted = {away_id, home_id}
    candidates: dict[str, dict[str, Any]] = {}

    for team_id in (away_id, home_id):
        try:
            payload, _ = frozen_history._fetch_team_schedule(team_id, year)
        except Exception:
            payload = {}
        for event in payload.get("events") or []:
            if not isinstance(event, Mapping):
                continue
            if _event_team_ids(event) != wanted:
                continue
            distance = _event_date_distance_hours(event, target)
            if target is not None and distance > 36.0:
                continue
            event_id = _clean(event.get("id") or _competition(event).get("id"))
            if not event_id:
                continue
            row = dict(event)
            row["_distance_hours"] = distance
            candidates[event_id] = row

    if not candidates:
        return {}
    return min(
        candidates.values(),
        key=lambda row: float(row.get("_distance_hours") or 0.0),
    )


def _rebuild_environment_from_event(
    base: Mapping[str, Any],
    event: Mapping[str, Any],
    away_id: str,
    home_id: str,
    source: str,
) -> dict[str, Any]:
    event_id = _clean(event.get("id") or _competition(event).get("id"))
    if not event_id:
        return dict(base)

    try:
        summary, summary_attempts = frozen_environment._fetch_summary(event_id)
    except Exception:
        summary, summary_attempts = {}, []

    identity_ready = frozen_environment._summary_identity_matches(
        summary,
        event_id,
    )
    weather = frozen_environment._weather(summary) if identity_ready else {}
    venue = frozen_environment._venue(summary) if identity_ready else {}
    if weather.get("ready"):
        stress = frozen_environment._weather_stress(weather, venue)
    else:
        stress = {
            "gust_stress": 0.0,
            "precipitation_stress": 0.0,
            "temperature_stress": 0.0,
            "total_stress": 0.0,
            "sigma_adjustment": 0.0,
            "indoor_weather_neutralized": False,
        }

    try:
        away_payload, away_attempts = frozen_environment._fetch_roster(away_id)
    except Exception:
        away_payload, away_attempts = {}, []
    try:
        home_payload, home_attempts = frozen_environment._fetch_roster(home_id)
    except Exception:
        home_payload, home_attempts = {}, []

    away_availability = frozen_environment._roster_audit(away_payload, away_id)
    home_availability = frozen_environment._roster_audit(home_payload, home_id)
    roster_coverage = (
        float(bool(away_availability.get("ready")))
        + float(bool(home_availability.get("ready")))
    ) / 2.0

    sides = frozen_environment._side_meta(event)
    model_ready = bool(identity_ready and weather.get("ready"))
    reason = ""
    if not model_ready:
        reason = (
            "recovered ESPN event summary identity did not verify"
            if not identity_ready
            else "recovered game-time weather fields are incomplete"
        )

    coverage = (
        float(identity_ready)
        + float(bool(weather.get("ready")))
        + float(bool(venue.get("ready")))
    ) / 3.0

    out = dict(base)
    out.update({
        "version": MODEL_VERSION,
        "model_ready": model_ready,
        "reason": reason,
        "event_id": event_id,
        "same_date_event_identity_verified": bool(identity_ready),
        "away_espn_team_id": away_id,
        "home_espn_team_id": home_id,
        "away_event_team": (sides.get("away") or {}).get("display_name"),
        "home_event_team": (sides.get("home") or {}).get("display_name"),
        "weather": weather,
        "venue": venue,
        "weather_stress": stress,
        "sigma_adjustment": float(stress.get("sigma_adjustment") or 0.0),
        "coverage": float(coverage),
        "away_availability": away_availability,
        "home_availability": home_availability,
        "roster_audit_coverage": float(roster_coverage),
        "recovery_used": True,
        "recovery_source": source,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "diagnostics": {
            **dict(base.get("diagnostics") or {}),
            "recovered_summary_attempts": summary_attempts,
            "recovered_away_roster_attempts": away_attempts,
            "recovered_home_roster_attempts": home_attempts,
        },
    })
    return out


def build_environment_engine(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    base = _FROZEN_ENV_BUILD(game, away, home)
    if base.get("model_ready"):
        out = dict(base)
        out["recovery_used"] = False
        out["recovery_source"] = "Step 9 exact-event"
        return out

    ids = resolve_espn_team_ids(game, away, home, base)
    if not ids.get("ready"):
        out = dict(base)
        out["recovery_used"] = False
        out["recovery_source"] = "unresolved"
        return out

    away_id = _clean(ids.get("away_team_id"))
    home_id = _clean(ids.get("home_team_id"))
    event = _find_event_from_team_schedules(game, away_id, home_id)
    if event:
        return _rebuild_environment_from_event(
            base,
            event,
            away_id,
            home_id,
            f"{ids.get('source')} + ESPN team schedule exact pair/date",
        )

    out = dict(base)
    out.update({
        "away_espn_team_id": away_id,
        "home_espn_team_id": home_id,
        "recovery_used": True,
        "recovery_source": _clean(ids.get("source")),
        "reason": (
            _clean(base.get("reason"))
            + "; ESPN team IDs recovered, but exact event is still unavailable"
        ).strip("; "),
    })
    return out


def _slug_guess(name: str) -> str:
    key = _key(name)
    if key in _WINSIPEDIA_SLUG_OVERRIDES:
        return _WINSIPEDIA_SLUG_OVERRIDES[key]
    text = _clean(name).lower()
    text = text.replace("(fl)", "fl").replace("(oh)", "oh")
    text = text.replace("&", "and")
    text = re.sub(r"['’]", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_tr = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif self.in_tr and tag in {"td", "th"}:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self.in_cell:
            text = " ".join("".join(self.current_cell).split())
            self.current_row.append(unescape(text))
            self.current_cell = []
            self.in_cell = False
        elif tag == "tr" and self.in_tr:
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = []
            self.in_tr = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


@st.cache_data(ttl=21600, show_spinner=False)
def _fetch_winsipedia_games(away_name: str, home_name: str) -> dict[str, Any]:
    away_slug = _slug_guess(away_name)
    home_slug = _slug_guess(home_name)
    if not away_slug or not home_slug:
        return {}
    url = f"{WINSIPEDIA_BASE}/games/{away_slug}/vs/{home_slug}"
    try:
        response = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": "KyreSportsAI/1.0"},
        )
        if response.status_code != 200:
            return {}
        parser = _TableParser()
        parser.feed(response.text)
    except Exception:
        return {}

    rows: list[dict[str, Any]] = []
    for cells in parser.rows:
        if len(cells) < 4:
            continue
        date = next(
            (cell for cell in cells[:2] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cell)),
            "",
        )
        if not date:
            continue
        score_cells = cells[2:4]
        scores: list[int] = []
        for cell in score_cells:
            found = re.findall(r"\b(\d{1,3})\b", cell)
            if not found:
                break
            scores.append(int(found[-1]))
        if len(scores) != 2:
            continue
        rows.append({
            "date": date,
            "away_points": scores[0],
            "home_points": scores[1],
            "combined_total": scores[0] + scores[1],
            "source": "Winsipedia game-by-game",
            "source_url": url,
        })

    if not rows:
        return {}
    rows.sort(key=lambda row: row["date"], reverse=True)
    totals = [float(row["combined_total"]) for row in rows]
    away_wins = sum(row["away_points"] > row["home_points"] for row in rows)
    home_wins = sum(row["home_points"] > row["away_points"] for row in rows)
    ties = len(rows) - away_wins - home_wins
    return {
        "ready": True,
        "source": "Winsipedia",
        "source_url": url,
        "away_name": away_name,
        "home_name": home_name,
        "meetings": len(rows),
        "away_wins": away_wins,
        "home_wins": home_wins,
        "ties": ties,
        "avg_combined_total": float(fmean(totals)),
        "combined_total_sigma": float(pstdev(totals)) if len(totals) > 1 else 0.0,
        "latest": dict(rows[0]),
        "sample": rows,
        "projection_weight": EXTERNAL_HISTORY_PROJECTION_WEIGHT,
        "selection_weight": EXTERNAL_HISTORY_SELECTION_WEIGHT,
        "analysis_line_weight": EXTERNAL_HISTORY_ANALYSIS_LINE_WEIGHT,
    }


def build_history_engine(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    step9_environment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    env = dict(step9_environment or {})
    if not env:
        env = build_environment_engine(game, away, home)

    base = _FROZEN_HISTORY_BUILD(
        game,
        away,
        home,
        step9_environment=env,
    )

    away_name = _clean(game.get("away_team") or away.get("team"))
    home_name = _clean(game.get("home_team") or home.get("team"))
    external = _fetch_winsipedia_games(away_name, home_name)

    out = dict(base)
    out["all_time_head_to_head"] = dict(external)
    out["external_history_source_used"] = bool(external.get("ready"))
    out["external_history_projection_weight"] = 0.0
    out["external_history_selection_weight"] = 0.0
    out["external_history_analysis_line_weight"] = 0.0

    # If ESPN IDs are recovered, preserve them even if one upstream Step-9
    # environment field remains gated.
    if env.get("away_espn_team_id"):
        out["away_espn_team_id"] = _clean(env.get("away_espn_team_id"))
    if env.get("home_espn_team_id"):
        out["home_espn_team_id"] = _clean(env.get("home_espn_team_id"))

    # For Step-10 display readiness, a verified all-time series can prevent a
    # blank H2H panel. It remains context-only and cannot change projection math.
    if external.get("ready"):
        out["context_ready"] = True
        out["recovery_used"] = True
        out["recovery_source"] = (
            (_clean(out.get("recovery_source")) + " + Winsipedia H2H")
            .strip(" +")
        )

    return out


def clear_recovery_cache() -> None:
    for fn in (_fetch_espn_teams, _fetch_winsipedia_games):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "EXTERNAL_HISTORY_ANALYSIS_LINE_WEIGHT",
    "EXTERNAL_HISTORY_PROJECTION_WEIGHT",
    "EXTERNAL_HISTORY_SELECTION_WEIGHT",
    "FROZEN_STEP12_COMPLETE",
    "MODEL_VERSION",
    "_fetch_winsipedia_games",
    "_find_event_from_team_schedules",
    "_resolve_team_id_from_directory",
    "build_environment_engine",
    "build_history_engine",
    "clear_recovery_cache",
    "resolve_espn_team_ids",
]
