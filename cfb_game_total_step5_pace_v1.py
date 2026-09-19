"""CFB Game Total Step 5 — Pace & Expected Possessions V1.

Presentation/evidence-only Step 5 owner for the Game Total page.

Verified sources
----------------
- NCAA Total Offense: offensive plays / game.
- NCAA Time of Possession: possession-clock seconds / offensive play.
- Punt & Rally verified snapshot: points / drive for drive-count fallback estimates.
- SportsDataverse GitHub game JSON: direct drive counts, average drive time,
  no-huddle text markers, and a conservative situation-neutral pace sample.
- ESPN summaries are optional last-resort recovery only, never required.

This module never mutates projection/probability/model outputs. The certified
pace engine is read-only here; sportsbook projection influence remains 0.0%.
"""
from __future__ import annotations

from statistics import mean
from html import escape
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import re
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

import requests
import streamlit as st

import cfb_over_under_pace_engine_v1 as pace_engine
import cfb_game_total_step2_drive_v1 as drive_source

MODEL_VERSION = "CFB GAME TOTAL STEP 5 • V168 PACE & EXPECTED POSSESSIONS"
STEP5_PRESENTATION_MARKER = "CFB_GAME_TOTAL_STEP5_PACE_POSSESSIONS_ACTIVE"
STEP5_DATA_MARKER = "CFB_GAME_TOTAL_STEP5_NCAA_PBP_MULTISOURCE_ACTIVE"
STEP5_VISUAL_MARKER = "CFB_GAME_TOTAL_STEP5_V168_VISUAL_TARGET_ACTIVE"
STEP5_DEPLOYMENT_MARKER = "CFB_GAME_TOTAL_STEP5_V178_NONBLOCKING_ACTIVE"
FROZEN_PREDECESSOR = "cfb_game_total_clean_page_v16"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

SPORTSDATAVERSE_GAME_URL = (
    "https://raw.githubusercontent.com/sportsdataverse/"
    "cfbfastR-cfb-raw/main/cfb/json/final/{event_id}.json"
)
SPORTSDATAVERSE_TIMEOUT_SECONDS = 5.0
ESPN_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/"
    "college-football/summary"
)
ESPN_TIMEOUT_SECONDS = 4.0
MAX_PBP_GAMES = 2

_ALLOWED_STATE = {"READY", "CHECK", "DATA LIMITED"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _pct(value: Any) -> str:
    number = _float(value)
    return "—" if number is None else f"{100.0 * number:.0f}%"


def _num(value: Any, digits: int = 1) -> str:
    number = _float(value)
    return "—" if number is None else f"{number:.{digits}f}"


def _clock_seconds(value: Any) -> float | None:
    text = _clean(value)
    if not text:
        return None
    if ":" not in text:
        return _float(text)
    parts = text.split(":")
    try:
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            if minutes < 0 or seconds < 0 or seconds >= 60:
                return None
            return 60.0 * minutes + seconds
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            if min(hours, minutes, seconds) < 0 or minutes >= 60 or seconds >= 60:
                return None
            return 3600.0 * hours + 60.0 * minutes + seconds
    except ValueError:
        return None
    return None


def _duration_text(seconds: Any) -> str:
    value = _float(seconds)
    if value is None or value < 0:
        return "—"
    rounded = int(round(value))
    return f"{rounded // 60}:{rounded % 60:02d}"


def _team_identity(identity: Mapping[str, Any], side: str) -> dict[str, Any]:
    row = identity.get(side) if isinstance(identity.get(side), Mapping) else {}
    return dict(row or {})


def _team_name(
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    side: str,
) -> str:
    row = _team_identity(identity, side)
    return (
        _clean(row.get("team"))
        or _clean(profile.get("team"))
        or _clean(profile.get("team_name"))
        or side.title()
    )


def _team_id(
    identity: Mapping[str, Any],
    side: str,
    profile: Mapping[str, Any] | None = None,
) -> str:
    row = _team_identity(identity, side)
    profile = profile or {}
    for source in (row, profile):
        for key in ("team_id", "espn_team_id", "id"):
            value = _clean(source.get(key))
            if value.isdigit():
                return value
    return ""


def _logo(identity: Mapping[str, Any], side: str) -> str:
    row = _team_identity(identity, side)
    return _clean(row.get("logo"))


def _record(profile: Mapping[str, Any]) -> str:
    value = profile.get("record_text")
    if value not in (None, "", "—"):
        return _clean(value)
    record = profile.get("record")
    if isinstance(record, Mapping):
        wins = _int(record.get("wins"))
        losses = _int(record.get("losses"))
        if wins is not None and losses is not None:
            return f"{wins}-{losses}"
    text = _clean(record)
    return text if text and text != "—" else "—"


def _conference(identity: Mapping[str, Any], profile: Mapping[str, Any], side: str) -> str:
    row = _team_identity(identity, side)
    return _clean(row.get("conference")) or _clean(profile.get("conference")) or "NCAAF"


def _event_ids(profile: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    completed = profile.get("completed_games") or []
    if not isinstance(completed, Sequence) or isinstance(completed, (str, bytes)):
        return out
    for row in reversed(list(completed)):
        if not isinstance(row, Mapping):
            continue
        value = ""
        for key in ("event_id", "espn_event_id", "game_id", "id"):
            value = _clean(row.get(key))
            if value:
                break
        if value and value not in out:
            out.append(value)
        if len(out) >= MAX_PBP_GAMES:
            break
    return out


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_sportsdataverse_game(event_id: str) -> dict[str, Any]:
    event_id = _clean(event_id)
    if not event_id:
        return {}
    url = SPORTSDATAVERSE_GAME_URL.format(event_id=event_id)
    try:
        response = requests.get(
            url,
            timeout=SPORTSDATAVERSE_TIMEOUT_SECONDS,
            headers={
                "User-Agent": "KyreSportsAI-GameTotal-Step5/1.0",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_summary(event_id: str) -> dict[str, Any]:
    event_id = _clean(event_id)
    if not event_id:
        return {}
    try:
        response = requests.get(
            ESPN_SUMMARY_URL,
            params={"event": event_id},
            timeout=ESPN_TIMEOUT_SECONDS,
            headers={
                "User-Agent": "KyreSportsAI-GameTotal-Step5/1.0",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _drive_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("drives")
    rows: list[dict[str, Any]] = []
    if isinstance(raw, Mapping):
        for key in ("previous", "current"):
            value = raw.get(key)
            if isinstance(value, list):
                rows.extend(dict(item) for item in value if isinstance(item, Mapping))
            elif isinstance(value, Mapping):
                rows.append(dict(value))
    elif isinstance(raw, list):
        rows.extend(dict(item) for item in raw if isinstance(item, Mapping))
    return rows


def _drive_team_id(drive: Mapping[str, Any]) -> str:
    team = drive.get("team") if isinstance(drive.get("team"), Mapping) else {}
    return _clean(team.get("id") or drive.get("teamId") or drive.get("team_id"))


def _play_period(play: Mapping[str, Any]) -> int | None:
    period = play.get("period")
    if isinstance(period, Mapping):
        value = _int(period.get("number") or period.get("value"))
        if value is not None:
            return value
    value = _int(period)
    if value is not None:
        return value
    return _int(play.get("period.number"))


def _play_clock(play: Mapping[str, Any]) -> float | None:
    clock = play.get("clock")
    if isinstance(clock, Mapping):
        value = _clock_seconds(clock.get("displayValue") or clock.get("value"))
        if value is not None:
            return value
    value = _clock_seconds(clock)
    if value is not None:
        return value
    return _clock_seconds(play.get("clock.displayValue"))


def _score_margin(play: Mapping[str, Any]) -> float | None:
    home = _float(play.get("homeScore") or play.get("home_score"))
    away = _float(play.get("awayScore") or play.get("away_score"))
    if home is None or away is None:
        return None
    return abs(home - away)


def _drive_time_seconds(drive: Mapping[str, Any]) -> float | None:
    elapsed = drive.get("timeElapsed")
    if isinstance(elapsed, Mapping):
        return _clock_seconds(elapsed.get("displayValue") or elapsed.get("value"))
    return _clock_seconds(elapsed)


def _drive_plays(drive: Mapping[str, Any]) -> list[dict[str, Any]]:
    plays = drive.get("plays")
    return [dict(item) for item in plays or [] if isinstance(item, Mapping)]


def _neutral_play_deltas(plays: Sequence[Mapping[str, Any]]) -> list[float]:
    deltas: list[float] = []
    previous: tuple[int, float] | None = None
    for play in plays:
        period = _play_period(play)
        clock = _play_clock(play)
        margin = _score_margin(play)
        if period is None or clock is None or period > 4:
            previous = None
            continue
        if period in {2, 4} and clock <= 120.0:
            previous = None
            continue
        if margin is not None and margin > 14.0:
            previous = None
            continue
        if previous is not None and previous[0] == period:
            delta = previous[1] - clock
            if 5.0 <= delta <= 45.0:
                deltas.append(float(delta))
        previous = (period, clock)
    return deltas


def _sdv_offense_team_id(play: Mapping[str, Any]) -> str:
    participants = play.get("teamParticipants") or []
    if isinstance(participants, Sequence) and not isinstance(participants, (str, bytes)):
        for item in participants:
            if not isinstance(item, Mapping):
                continue
            if _clean(item.get("type")).casefold() != "offense":
                continue
            team = item.get("team") if isinstance(item.get("team"), Mapping) else {}
            value = _clean(item.get("id") or team.get("id"))
            if value:
                return value
    return _clean(play.get("start.team.id"))


def _sdv_is_scrimmage(play: Mapping[str, Any]) -> bool:
    down = _int(play.get("start.down"))
    if down not in {1, 2, 3, 4}:
        return False
    play_type = _clean(play.get("type.text")).casefold()
    blocked = (
        "kickoff",
        "punt",
        "field goal",
        "extra point",
        "timeout",
        "end period",
        "end of",
    )
    return not any(token in play_type for token in blocked)


def _sdv_drive_seconds(play: Mapping[str, Any]) -> float | None:
    return _clock_seconds(play.get("drive.timeElapsed.displayValue"))


def _parse_sportsdataverse_evidence(
    games: Sequence[Mapping[str, Any]],
    team_id: str,
) -> dict[str, Any]:
    team_id = _clean(team_id)
    games_with_drives = 0
    total_drives = 0
    drive_seconds: list[float] = []
    neutral_deltas: list[float] = []
    no_huddle_plays = 0
    scrimmage_plays = 0

    for payload in games:
        raw_plays = payload.get("plays") or []
        plays = [
            dict(item)
            for item in raw_plays
            if isinstance(item, Mapping)
            and _sdv_offense_team_id(item) == team_id
            and _sdv_is_scrimmage(item)
        ]
        if not plays:
            continue

        drive_map: dict[str, float | None] = {}
        plays_by_drive: dict[str, list[dict[str, Any]]] = {}
        for play in plays:
            drive_id = _clean(play.get("drive.id"))
            if not drive_id:
                continue
            if drive_id not in drive_map:
                drive_map[drive_id] = _sdv_drive_seconds(play)
            plays_by_drive.setdefault(drive_id, []).append(play)

        if drive_map:
            games_with_drives += 1
            total_drives += len(drive_map)
            for value in drive_map.values():
                if value is not None and 10.0 <= value <= 900.0:
                    drive_seconds.append(float(value))
            for drive_plays in plays_by_drive.values():
                neutral_deltas.extend(_neutral_play_deltas(drive_plays))

        for play in plays:
            text = _clean(play.get("text"))
            if not text:
                continue
            scrimmage_plays += 1
            lower = text.casefold()
            if "no huddle" in lower or "no-huddle" in lower:
                no_huddle_plays += 1

    drives_pg = (
        float(total_drives) / float(games_with_drives)
        if games_with_drives > 0 and total_drives > 0
        else None
    )
    plays_pg = (
        float(scrimmage_plays) / float(games_with_drives)
        if games_with_drives > 0 and scrimmage_plays > 0
        else None
    )
    avg_drive = mean(drive_seconds) if drive_seconds else None
    neutral_pace = mean(neutral_deltas) if neutral_deltas else None
    no_huddle = (
        float(no_huddle_plays) / float(scrimmage_plays)
        if scrimmage_plays > 0
        else None
    )
    return {
        "games": games_with_drives,
        "drive_count": total_drives,
        "drives_per_game": drives_pg,
        "plays_per_game": plays_pg,
        "seconds_per_play": neutral_pace,
        "avg_drive_time_seconds": avg_drive,
        "situation_neutral_seconds_per_play": neutral_pace,
        "no_huddle_rate": no_huddle,
        "text_plays": scrimmage_plays,
        "no_huddle_plays": no_huddle_plays,
        "source": (
            "SportsDataverse current-season completed-game PBP"
            if games_with_drives > 0
            else ""
        ),
        "delivery": "sportsdataverse_github_raw",
    }


def _parse_drive_evidence(
    summaries: Sequence[Mapping[str, Any]],
    team_id: str,
) -> dict[str, Any]:
    team_id = _clean(team_id)
    games_with_drives = 0
    drive_count = 0
    drive_seconds: list[float] = []
    neutral_deltas: list[float] = []
    no_huddle_plays = 0
    text_plays = 0

    for payload in summaries:
        team_drives = [
            drive
            for drive in _drive_rows(payload)
            if team_id and _drive_team_id(drive) == team_id
        ]
        if not team_drives:
            continue
        games_with_drives += 1
        drive_count += len(team_drives)
        for drive in team_drives:
            elapsed = _drive_time_seconds(drive)
            if elapsed is not None and 10.0 <= elapsed <= 900.0:
                drive_seconds.append(float(elapsed))
            plays = _drive_plays(drive)
            neutral_deltas.extend(_neutral_play_deltas(plays))
            for play in plays:
                text = _clean(play.get("text") or play.get("description"))
                if not text:
                    continue
                text_plays += 1
                lower = text.casefold()
                if "no huddle" in lower or "no-huddle" in lower:
                    no_huddle_plays += 1

    drives_pg = (
        float(drive_count) / float(games_with_drives)
        if games_with_drives > 0 and drive_count > 0
        else None
    )
    avg_drive = mean(drive_seconds) if drive_seconds else None
    neutral_pace = mean(neutral_deltas) if neutral_deltas else None
    no_huddle = (
        float(no_huddle_plays) / float(text_plays)
        if text_plays > 0
        else None
    )
    return {
        "games": games_with_drives,
        "drive_count": drive_count,
        "drives_per_game": drives_pg,
        "avg_drive_time_seconds": avg_drive,
        "situation_neutral_seconds_per_play": neutral_pace,
        "no_huddle_rate": no_huddle,
        "text_plays": text_plays,
        "no_huddle_plays": no_huddle_plays,
        "source": (
            "ESPN completed-game drive/play-by-play"
            if games_with_drives > 0
            else ""
        ),
    }


def _safe_drive_evidence(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    profiles = {"away": away, "home": home}
    side_events = {
        side: _event_ids(profile)
        for side, profile in profiles.items()
    }
    unique_events = list(
        dict.fromkeys(
            event_id
            for ids in side_events.values()
            for event_id in ids
        )
    )

    sdv_payloads: dict[str, dict[str, Any]] = {}
    if unique_events:
        with ThreadPoolExecutor(max_workers=min(4, len(unique_events))) as pool:
            results = list(pool.map(_fetch_sportsdataverse_game, unique_events))
        sdv_payloads = {
            event_id: payload
            for event_id, payload in zip(unique_events, results)
            if payload
        }

    out: dict[str, Any] = {}
    for side, profile in profiles.items():
        event_ids = side_events[side]
        team_id = _team_id(identity, side, profile)
        sdv_games = [
            sdv_payloads[event_id]
            for event_id in event_ids
            if event_id in sdv_payloads
        ]
        row = _parse_sportsdataverse_evidence(sdv_games, team_id)

        # Direct ESPN summary is a last-resort recovery only. Production does
        # not require it because deployed Streamlit has observed ESPN 403s.
        fallback_used = False
        if not row.get("games"):
            summaries = [_fetch_summary(event_id) for event_id in event_ids]
            summaries = [payload for payload in summaries if payload]
            fallback = _parse_drive_evidence(summaries, team_id)
            if fallback.get("games"):
                row = fallback
                row["delivery"] = "espn_summary_last_resort"
                fallback_used = True

        row["team_id"] = team_id
        row["requested_event_ids"] = event_ids
        row["sportsdataverse_games_loaded"] = len(sdv_games)
        row["espn_fallback_used"] = fallback_used
        out[side] = row
    return out


def _safe_sdv_pregame_pace(
    identity: Mapping[str, Any],
    game: Mapping[str, Any],
    drive_evidence: Mapping[str, Any],
    frozen_pace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Presentation-only recovery from already-certified completed-game PBP.

    This path never becomes model-ready and never mutates projection math. It
    exists only so Step 5 can render verified play volume/tempo when the NCAA
    HTML pace tables are temporarily unavailable.
    """
    frozen = dict(frozen_pace or {})
    frozen_away = (
        frozen.get("away")
        if isinstance(frozen.get("away"), Mapping)
        else {}
    )
    frozen_home = (
        frozen.get("home")
        if isinstance(frozen.get("home"), Mapping)
        else {}
    )

    raw: dict[str, dict[str, Any]] = {}
    for side in ("away", "home"):
        drive = (
            drive_evidence.get(side)
            if isinstance(drive_evidence.get(side), Mapping)
            else {}
        )
        plays_pg = _float(drive.get("plays_per_game"))
        spp = _float(
            drive.get("seconds_per_play")
            or drive.get("situation_neutral_seconds_per_play")
        )
        raw[side] = {
            "drive": dict(drive),
            "plays_per_game": plays_pg,
            "seconds_per_play": spp,
        }

    away_ppg = raw["away"]["plays_per_game"]
    home_ppg = raw["home"]["plays_per_game"]
    away_spp = raw["away"]["seconds_per_play"]
    home_spp = raw["home"]["seconds_per_play"]

    if away_ppg is None or home_ppg is None:
        return {
            "ready": True,
            "model_ready": False,
            "presentation_ready": False,
            "coverage": 0.0,
            "reason": "SportsDataverse completed-game PBP pace fallback incomplete",
            "away": {},
            "home": {},
            "sportsbook_input_used": False,
        }

    baseline_candidates = [
        _float(frozen_away.get("division_baseline_plays_per_game")),
        _float(frozen_home.get("division_baseline_plays_per_game")),
    ]
    baseline_values = [
        value for value in baseline_candidates
        if value is not None and value > 0
    ]
    # If NCAA loaded a division baseline but missed one/both team rows, preserve
    # that authoritative baseline. Otherwise use the two-team midpoint only as
    # a neutral presentation reference; it cannot influence model math.
    baseline_plays = (
        mean(baseline_values)
        if baseline_values
        else (float(away_ppg) + float(home_ppg)) / 2.0
    )

    side_contracts: dict[str, dict[str, Any]] = {}
    frozen_by_side = {"away": frozen_away, "home": frozen_home}
    for side in ("away", "home"):
        plays_pg = float(raw[side]["plays_per_game"])
        spp = _float(raw[side]["seconds_per_play"])
        drive = raw[side]["drive"]
        frozen_row = frozen_by_side[side]
        games = _int(drive.get("games")) or 0
        side_contracts[side] = {
            "team": _clean(_team_identity(identity, side).get("team")),
            "games": games,
            "plays_per_game": plays_pg,
            "seconds_per_offensive_play": spp,
            "avg_time_of_possession_seconds": None,
            "division_baseline_plays_per_game": baseline_plays,
            "division_baseline_seconds_per_play": _float(
                frozen_row.get("division_baseline_seconds_per_play")
            ),
            "pace_index": (
                plays_pg / float(baseline_plays)
                if baseline_plays > 0
                else None
            ),
            "plays_rank": None,
            "seconds_per_play_rank": None,
            "rank_field_size": 0,
            "plays_source": "SportsDataverse completed-game PBP",
            "clock_source": "SportsDataverse completed-game PBP",
        }

    historical_combined = float(away_ppg) + float(home_ppg)
    baseline_combined = 2.0 * float(baseline_plays)
    pace_ratio = (
        historical_combined / baseline_combined
        if baseline_combined > 0
        else 1.0
    )
    pace_signal = max(
        -1.0,
        min(
            1.0,
            (pace_ratio - 1.0) / float(pace_engine.PACE_FULL_SIGNAL_RATIO),
        ),
    )
    clock_implied = (
        7200.0 / (float(away_spp) + float(home_spp))
        if away_spp is not None
        and home_spp is not None
        and float(away_spp) + float(home_spp) > 0
        else None
    )
    min_games = min(
        _int(raw["away"]["drive"].get("games")) or 0,
        _int(raw["home"]["drive"].get("games")) or 0,
    )
    sample_factor = max(0.0, min(1.0, float(min_games) / float(MAX_PBP_GAMES)))
    coverage = 1.0 if away_spp is not None and home_spp is not None else 0.90

    return {
        "ready": True,
        "model_ready": False,
        "presentation_ready": True,
        "presentation_source": "SportsDataverse completed-game PBP",
        "coverage": coverage,
        "sample_factor": sample_factor,
        "historical_combined_plays_per_game": historical_combined,
        "clock_implied_combined_plays": clock_implied,
        "division_baseline_combined_plays": baseline_combined,
        "expected_combined_plays": historical_combined,
        "pace_ratio": pace_ratio,
        "pace_signal": pace_signal,
        "pace_label": (
            "FAST" if pace_ratio >= 1.055
            else "SLOW" if pace_ratio <= 0.945
            else "NEUTRAL"
        ),
        "away": side_contracts["away"],
        "home": side_contracts["home"],
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }

def _profile_pace_seed(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Reuse already-enriched pace fields without making new live NCAA calls."""
    plays_pg = None
    for key in (
        "plays_per_game",
        "offensive_plays_per_game",
        "off_plays_per_game",
    ):
        plays_pg = _float(profile.get(key))
        if plays_pg is not None:
            break

    seconds_per_play = None
    for key in (
        "seconds_per_offensive_play",
        "seconds_per_play",
        "off_seconds_per_play",
    ):
        seconds_per_play = _float(profile.get(key))
        if seconds_per_play is not None:
            break

    baseline = _float(profile.get("division_baseline_plays_per_game"))
    pace_index = (
        float(plays_pg) / float(baseline)
        if plays_pg is not None and baseline is not None and baseline > 0
        else None
    )
    return {
        "team": _clean(profile.get("team")),
        "games": _int(profile.get("games")),
        "plays_per_game": plays_pg,
        "seconds_per_offensive_play": seconds_per_play,
        "avg_time_of_possession_seconds": _float(
            profile.get("avg_time_of_possession_seconds")
        ),
        "division_baseline_plays_per_game": baseline,
        "division_baseline_seconds_per_play": _float(
            profile.get("division_baseline_seconds_per_play")
        ),
        "pace_index": pace_index,
        "plays_source": (
            _clean(profile.get("plays_source"))
            if plays_pg is not None
            else ""
        ),
        "clock_source": (
            _clean(profile.get("clock_source"))
            if seconds_per_play is not None
            else ""
        ),
    }


def _safe_pace_engine(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    """Nonblocking Step-5 presentation seed.

    The frozen NCAA pace engine remains available to the certified model path,
    but the Streamlit presentation no longer waits on its multi-transport live
    scraper. Step 5 immediately reuses any already-enriched pace fields, then
    the existing SportsDataverse PBP recovery fills missing presentation data.
    """
    away_seed = _profile_pace_seed(away)
    home_seed = _profile_pace_seed(home)
    available = sum(
        value is not None
        for value in (
            away_seed.get("plays_per_game"),
            away_seed.get("seconds_per_offensive_play"),
            home_seed.get("plays_per_game"),
            home_seed.get("seconds_per_offensive_play"),
        )
    )
    return {
        "ready": True,
        "model_ready": False,
        "presentation_ready": False,
        "reason": "Live NCAA presentation scrape deferred; using verified preloaded/PBP evidence",
        "away": away_seed,
        "home": home_seed,
        "coverage": available / 4.0,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "presentation_ncaa_live_fetch_used": False,
    }


def _season(display_game: Mapping[str, Any]) -> int:
    for key in ("game_date", "date", "start_date", "kickoff_iso"):
        text = _clean(display_game.get(key))
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
    return 2026


def _with_drive_ppd(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    season: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    away_out, home_out = dict(away), dict(home)
    try:
        return drive_source.enrich_step2_drive_metrics(
            away_out,
            home_out,
            int(season),
        )
    except Exception as exc:
        return away_out, home_out, {
            "status": "CHECK",
            "source": "Punt & Rally",
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }


def _profile_ppg(profile: Mapping[str, Any]) -> float | None:
    for key in ("ppg", "points_per_game", "scoring_offense_pg"):
        value = _float(profile.get(key))
        if value is not None:
            return value
    return None


def _estimated_drives(
    profile: Mapping[str, Any],
    direct: Mapping[str, Any],
) -> tuple[float | None, str]:
    direct_value = _float(direct.get("drives_per_game"))
    if direct_value is not None and direct_value > 0:
        return direct_value, "PBP"

    ppg = _profile_ppg(profile)
    ppd = _float(profile.get("points_per_drive"))
    if ppg is not None and ppd is not None and ppd > 0:
        value = ppg / ppd
        if 6.0 <= value <= 20.0:
            return value, "PPG÷PPD"
    return None, "DATA LIMITED"


def _avg_drive_time(
    pace_row: Mapping[str, Any],
    drives_pg: float | None,
    direct: Mapping[str, Any],
) -> tuple[float | None, str]:
    direct_value = _float(direct.get("avg_drive_time_seconds"))
    if direct_value is not None and direct_value > 0:
        return direct_value, "PBP"
    top = _float(pace_row.get("avg_time_of_possession_seconds"))
    if top is not None and drives_pg is not None and drives_pg > 0:
        value = top / drives_pg
        if 30.0 <= value <= 420.0:
            return value, "TOP÷DRIVES"
    return None, "DATA LIMITED"


def _pace_badge(pace_index: Any) -> str:
    value = _float(pace_index)
    if value is None:
        return "NCAA"
    if value >= 1.055:
        return "FAST"
    if value <= 0.945:
        return "SLOW"
    return "AVERAGE"


def _tile(
    label: str,
    value: str,
    badge: str,
    *,
    ready: bool,
    source: str,
    icon: str,
) -> dict[str, Any]:
    return {
        "label": label,
        "value": value if ready else "—",
        "badge": badge if ready else "DATA LIMITED",
        "ready": bool(ready),
        "source": source if ready else "",
        "icon": icon,
    }


def _team_contract(
    profile: Mapping[str, Any],
    pace_row: Mapping[str, Any],
    drive_row: Mapping[str, Any],
) -> dict[str, Any]:
    plays_pg = _float(pace_row.get("plays_per_game"))
    spp = _float(pace_row.get("seconds_per_offensive_play"))
    plays_rank = _int(pace_row.get("plays_rank"))
    neutral = _float(drive_row.get("situation_neutral_seconds_per_play"))
    no_huddle = _float(drive_row.get("no_huddle_rate"))
    drives_pg, drives_basis = _estimated_drives(profile, drive_row)
    drive_time, drive_time_basis = _avg_drive_time(
        pace_row,
        drives_pg,
        drive_row,
    )

    tiles = [
        _tile(
            "PLAYS / GAME",
            _num(plays_pg),
            f"#{plays_rank} FBS" if plays_rank is not None else (
                "SDV" if "SportsDataverse" in _clean(pace_row.get("plays_source")) else "NCAA"
            ),
            ready=plays_pg is not None,
            source=_clean(pace_row.get("plays_source")) or "NCAA Total Offense",
            icon="▶",
        ),
        _tile(
            "SECONDS / PLAY",
            _num(spp),
            _pace_badge(pace_row.get("pace_index")),
            ready=spp is not None,
            source=_clean(pace_row.get("clock_source")) or "NCAA Time of Possession",
            icon="⏱",
        ),
        _tile(
            "SITUATION-NEUTRAL PACE",
            f"{_num(neutral)} sec",
            "PBP",
            ready=neutral is not None,
            source=_clean(drive_row.get("source")),
            icon="▥",
        ),
        _tile(
            "DRIVES / GAME",
            _num(drives_pg),
            drives_basis,
            ready=drives_pg is not None,
            source=(
                _clean(drive_row.get("source"))
                if drives_basis == "PBP"
                else "NCAA scoring + Punt & Rally PPD"
            ),
            icon="✚",
        ),
        _tile(
            "NO-HUDDLE RATE",
            _pct(no_huddle),
            "PBP",
            ready=no_huddle is not None,
            source=_clean(drive_row.get("source")),
            icon="≫",
        ),
        _tile(
            "AVG DRIVE TIME",
            _duration_text(drive_time),
            drive_time_basis,
            ready=drive_time is not None,
            source=(
                _clean(drive_row.get("source"))
                if drive_time_basis == "PBP"
                else "NCAA TOP + drive estimate"
            ),
            icon="◷",
        ),
    ]
    return {
        "team": _clean(profile.get("team")),
        "tiles": tiles,
        "ready_tiles": sum(bool(row["ready"]) for row in tiles),
        "plays_per_game": plays_pg,
        "seconds_per_play": spp,
        "pace_index": _float(pace_row.get("pace_index")),
        "drives_per_game": drives_pg,
        "drives_basis": drives_basis,
        "avg_drive_time_seconds": drive_time,
        "drive_time_basis": drive_time_basis,
        "situation_neutral_seconds_per_play": neutral,
        "no_huddle_rate": no_huddle,
        "pbp_games": _int(drive_row.get("games")) or 0,
    }


def _tempo_grade(pace_ratio: Any) -> str:
    value = _float(pace_ratio)
    if value is None:
        return "—"
    if value >= 1.10:
        return "A"
    if value >= 1.055:
        return "A-"
    if value >= 1.02:
        return "B+"
    if value >= 0.98:
        return "B"
    if value >= 0.945:
        return "C+"
    return "C"


def _volatility(
    pace: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    sample = _float(pace.get("sample_factor")) or 0.0
    pbp_games = min(
        _int(away.get("pbp_games")) or 0,
        _int(home.get("pbp_games")) or 0,
    )
    historical = _float(pace.get("historical_combined_plays_per_game"))
    clock = _float(pace.get("clock_implied_combined_plays"))
    disagreement = (
        abs(historical - clock) / max(historical, 1.0)
        if historical is not None and clock is not None
        else 0.08
    )
    if sample >= 0.8 and pbp_games >= 2 and disagreement <= 0.08:
        return "LOW"
    if sample >= 0.4 and disagreement <= 0.15:
        return "MEDIUM"
    return "HIGH"


def _expected_drives(
    pace: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> tuple[float | None, float | None, float | None]:
    away_drives = _float(away.get("drives_per_game"))
    home_drives = _float(home.get("drives_per_game"))
    expected_plays = _float(pace.get("expected_combined_plays"))
    historical_plays = _float(pace.get("historical_combined_plays_per_game"))
    if (
        away_drives is None
        or home_drives is None
        or expected_plays is None
        or historical_plays is None
        or historical_plays <= 0
    ):
        return None, None, None
    scale = max(0.80, min(1.20, expected_plays / historical_plays))
    away_expected = away_drives * scale
    home_expected = home_drives * scale
    return away_expected, home_expected, away_expected + home_expected


def _accelerator(
    away_name: str,
    home_name: str,
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> tuple[str, str]:
    pairs = [
        (away_name, _float(away.get("pace_index")), _float(away.get("seconds_per_play"))),
        (home_name, _float(home.get("pace_index")), _float(home.get("seconds_per_play"))),
    ]
    available = [row for row in pairs if row[1] is not None]
    if not available:
        return "Verified pace edge unavailable", ""
    team, index, spp = max(available, key=lambda row: float(row[1] or 0.0))
    detail = (
        f"{_num(spp)} sec/play • pace index {_num(index, 2)}"
        if spp is not None
        else f"pace index {_num(index, 2)}"
    )
    return f"{team} tempo", detail


def _brake(
    away_name: str,
    home_name: str,
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> tuple[str, str]:
    pairs = [
        (away_name, _float(away.get("pace_index")), _float(away.get("avg_drive_time_seconds"))),
        (home_name, _float(home.get("pace_index")), _float(home.get("avg_drive_time_seconds"))),
    ]
    available = [row for row in pairs if row[1] is not None]
    if not available:
        return "Verified pace brake unavailable", ""
    team, index, drive_time = min(available, key=lambda row: float(row[1] or 99.0))
    detail = (
        f"{_duration_text(drive_time)} avg drive • pace index {_num(index, 2)}"
        if drive_time is not None
        else f"pace index {_num(index, 2)}"
    )
    return f"{team} possession pace", detail


def _matchup_read(pace: Mapping[str, Any]) -> tuple[str, str]:
    ratio = _float(pace.get("pace_ratio"))
    if ratio is None:
        return "PACE DATA LIMITED", "Verified combined pace could not be established."
    if ratio >= 1.055:
        return (
            "ABOVE-AVERAGE POSSESSION ENVIRONMENT",
            "The verified pace blend projects more offensive play volume than the division baseline.",
        )
    if ratio <= 0.945:
        return (
            "BELOW-AVERAGE POSSESSION ENVIRONMENT",
            "The verified pace blend projects fewer offensive opportunities than the division baseline.",
        )
    return (
        "AVERAGE POSSESSION ENVIRONMENT",
        "The two tempo profiles combine near the division baseline for expected play volume.",
    )


def _ou_impact(pace: Mapping[str, Any]) -> tuple[str, str]:
    signal = _float(pace.get("pace_signal"))
    if signal is None:
        return "NEUTRAL", "Verified pace impact is unavailable."
    if signal >= 0.20:
        return (
            "SLIGHT OVER PRESSURE",
            "Higher expected play volume creates additional scoring opportunities.",
        )
    if signal <= -0.20:
        return (
            "SLIGHT UNDER PRESSURE",
            "Lower expected play volume reduces total scoring opportunities.",
        )
    return (
        "NEUTRAL",
        "Expected play volume is close to the division baseline.",
    )


def build_step5_contract(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any] | None = None,
    *,
    pace: Mapping[str, Any] | None = None,
    drive_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    game = dict(display_game or {})
    away_ppd, home_ppd, ppd_diag = _with_drive_ppd(
        away,
        home,
        _season(game),
    )
    pace_result = dict(
        pace
        if pace is not None
        else _safe_pace_engine(game, away_ppd, home_ppd)
    )
    drives = dict(
        drive_evidence
        if drive_evidence is not None
        else _safe_drive_evidence(identity, away_ppd, home_ppd)
    )
    if not pace_result.get("model_ready"):
        try:
            recovered = _safe_sdv_pregame_pace(
                identity,
                game,
                drives,
                pace_result,
            )
        except Exception as exc:
            recovered = {
                "ready": True,
                "model_ready": False,
                "presentation_ready": False,
                "coverage": 0.0,
                "away": {},
                "home": {},
                "sportsbook_input_used": False,
                "reason": f"SportsDataverse PBP recovery failed: {type(exc).__name__}",
            }
        if recovered.get("presentation_ready"):
            recovered["frozen_pace_engine"] = pace_result
            pace_result = recovered

    away_drive = drives.get("away") if isinstance(drives.get("away"), Mapping) else {}
    home_drive = drives.get("home") if isinstance(drives.get("home"), Mapping) else {}
    away_pace = pace_result.get("away") if isinstance(pace_result.get("away"), Mapping) else {}
    home_pace = pace_result.get("home") if isinstance(pace_result.get("home"), Mapping) else {}

    away_contract = _team_contract(away_ppd, away_pace, away_drive)
    home_contract = _team_contract(home_ppd, home_pace, home_drive)
    away_name = _team_name(identity, away_ppd, "away")
    home_name = _team_name(identity, home_ppd, "home")

    away_expected, home_expected, combined_expected = _expected_drives(
        pace_result,
        away_contract,
        home_contract,
    )
    total_tiles = 12
    ready_tiles = away_contract["ready_tiles"] + home_contract["ready_tiles"]
    coverage = ready_tiles / float(total_tiles)

    core_ready = bool(
        pace_result.get("model_ready")
        or pace_result.get("presentation_ready")
    )
    if not core_ready:
        state = "DATA LIMITED"
    elif ready_tiles == total_tiles:
        state = "READY"
    else:
        state = "CHECK"

    accelerator, accelerator_detail = _accelerator(
        away_name,
        home_name,
        away_contract,
        home_contract,
    )
    brake, brake_detail = _brake(
        away_name,
        home_name,
        away_contract,
        home_contract,
    )
    read_title, read_detail = _matchup_read(pace_result)
    impact_title, impact_detail = _ou_impact(pace_result)

    data_confidence = round(
        100.0
        * (
            0.60 * min(1.0, max(0.0, _float(pace_result.get("coverage")) or 0.0))
            + 0.40 * coverage
        )
    )

    return {
        "version": MODEL_VERSION,
        "state": state if state in _ALLOWED_STATE else "CHECK",
        "ready": state == "READY",
        "away_name": away_name,
        "home_name": home_name,
        "away": away_contract,
        "home": home_contract,
        "ready_tiles": ready_tiles,
        "tile_count": total_tiles,
        "coverage": coverage,
        "expected_away_drives": away_expected,
        "expected_home_drives": home_expected,
        "expected_combined_drives": combined_expected,
        "expected_combined_plays": _float(pace_result.get("expected_combined_plays")),
        "tempo_grade": _tempo_grade(pace_result.get("pace_ratio")),
        "pace_volatility": _volatility(
            pace_result,
            away_contract,
            home_contract,
        ),
        "pace_label": _clean(pace_result.get("pace_label")) or "UNAVAILABLE",
        "matchup_read": read_title,
        "matchup_read_detail": read_detail,
        "biggest_accelerator": accelerator,
        "biggest_accelerator_detail": accelerator_detail,
        "biggest_brake": brake,
        "biggest_brake_detail": brake_detail,
        "ou_impact": impact_title,
        "ou_impact_detail": impact_detail,
        "data_confidence": data_confidence,
        "pace_engine": pace_result,
        "drive_evidence": drives,
        "ppd_diagnostics": ppd_diag,
        "sportsbook_projection_influence": 0.0,
        "may_modify_projection": False,
    }


def _team_logo_html(identity: Mapping[str, Any], side: str, name: str) -> str:
    logo = _logo(identity, side)
    if logo:
        return (
            f'<img class="gt168-step5-logo" src="{escape(logo, quote=True)}" '
            f'alt="{escape(name)} logo">'
        )
    initials = "".join(part[:1] for part in name.split() if part)[:2].upper() or "CF"
    return f'<div class="gt168-step5-logo-fallback">{escape(initials)}</div>'


def _team_header(
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    side: str,
    display_game: Mapping[str, Any] | None = None,
) -> str:
    name = _team_name(identity, profile, side)
    record = _record(profile)
    event_record = _clean((display_game or {}).get(f"{side}_record_summary"))
    if event_record and record in {"—", "0-0"}:
        record = event_record
    conf = _conference(identity, profile, side)
    label = "AWAY" if side == "away" else "HOME"
    return f"""
<div class="gt168-step5-teamhead {side}">
  {_team_logo_html(identity, side, name)}
  <div>
    <span>{label}</span>
    <b>{escape(name)}</b>
    <small>{escape(record)} • {escape(conf)}</small>
  </div>
</div>"""


def _game_context_html(display_game: Mapping[str, Any] | None) -> str:
    game = dict(display_game or {})
    kickoff = _clean(
        game.get("kickoff_iso")
        or game.get("date")
        or game.get("start_date")
    )
    day_text = _clean(game.get("game_date"))
    time_text = ""
    if kickoff:
        try:
            parsed = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(ZoneInfo("America/New_York"))
                day_text = parsed.strftime("%a, %b %d").upper()
                time_text = parsed.strftime("%-I:%M %p ET")
        except Exception:
            pass
    venue = _clean(game.get("venue") or game.get("venue_name"))
    broadcast = _clean(game.get("broadcast"))
    if not any((day_text, time_text, venue, broadcast)):
        return ""
    return f"""
<div class="gt168-step5-game-context">
  <b>{escape(day_text or "GAME DAY")}</b>
  {f'<strong>{escape(time_text)}</strong>' if time_text else ''}
  {f'<span>{escape(venue)}</span>' if venue else ''}
  {f'<small>{escape(broadcast)}</small>' if broadcast else ''}
</div>"""


def _tile_html(tile: Mapping[str, Any], side: str) -> str:
    ready = bool(tile.get("ready"))
    state = "ready" if ready else "limited"
    return f"""
<div class="gt168-step5-metric {state}" data-testid="gt168-step5-stat-tile" data-ready="{str(ready).lower()}">
  <div class="gt168-step5-metric-kicker"><i>{escape(_clean(tile.get('icon')))}</i><span>{escape(_clean(tile.get('label')))}</span></div>
  <strong>{escape(_clean(tile.get('value')))}</strong>
  <em>{escape(_clean(tile.get('badge')))}</em>
  <small>{escape(_clean(tile.get('source')) or 'Verified source unavailable')}</small>
</div>"""


def _profile_html(
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    contract: Mapping[str, Any],
    side: str,
) -> str:
    name = _team_name(identity, profile, side)
    tone = "away" if side == "away" else "home"
    subtitle = (
        "Verified tempo, play volume and possession evidence."
        if int(contract.get("ready_tiles") or 0) == 6
        else "Verified core pace with source-gated supplemental possession data."
    )
    tiles = "".join(_tile_html(tile, side) for tile in contract.get("tiles") or [])
    return f"""
<section class="gt168-step5-profile {tone}" data-testid="gt168-step5-{side}-profile">
  <div class="gt168-step5-profile-title"><b>{escape(name)} Pace Profile</b><span>{escape(subtitle)}</span></div>
  <div class="gt168-step5-metrics">{tiles}</div>
</section>"""


def _summary_metric(label: str, value: str, extra: str = "") -> str:
    return f"""
<div class="gt168-step5-summary-metric">
  <span>{escape(label)}</span>
  <b>{escape(value)}</b>
  {f'<small>{escape(extra)}</small>' if extra else ''}
</div>"""


def _insight_card(icon: str, label: str, title: str, detail: str, cls: str = "") -> str:
    return f"""
<div class="gt168-step5-insight {escape(cls)}">
  <div class="gt168-step5-insight-icon">{escape(icon)}</div>
  <div><span>{escape(label)}</span><b>{escape(title)}</b><small>{escape(detail)}</small></div>
</div>"""


def render_step5_html(
    status: str,
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any] | None = None,
    *,
    pace: Mapping[str, Any] | None = None,
    drive_evidence: Mapping[str, Any] | None = None,
) -> str:
    contract = build_step5_contract(
        identity,
        away,
        home,
        display_game,
        pace=pace,
        drive_evidence=drive_evidence,
    )
    state = _clean(contract.get("state")) or "CHECK"
    state_class = "ready" if state == "READY" else "check"
    coverage_pct = int(round(100.0 * float(contract.get("coverage") or 0.0)))
    drive_evidence = contract.get("drive_evidence") if isinstance(contract.get("drive_evidence"), Mapping) else {}
    away_drive = drive_evidence.get("away") if isinstance(drive_evidence.get("away"), Mapping) else {}
    home_drive = drive_evidence.get("home") if isinstance(drive_evidence.get("home"), Mapping) else {}
    away_delivery = _clean(away_drive.get("delivery"))
    home_delivery = _clean(home_drive.get("delivery"))
    away_pbp_games = _int(away_drive.get("sportsdataverse_games_loaded")) or 0
    home_pbp_games = _int(home_drive.get("sportsdataverse_games_loaded")) or 0

    away_profile = contract["away"]
    home_profile = contract["home"]
    away_name = contract["away_name"]
    home_name = contract["home_name"]

    header = f"""
<div class="gt168-step5-head">
  <div class="gt168-step5-title"><span>5</span><div><b>⏱️ STEP 5 — PACE & EXPECTED POSSESSIONS</b><small>How many offensive opportunities will this game realistically create?</small></div></div>
  <div class="gt168-step5-chips">
    <em>{escape(state)}</em>
    <em>{coverage_pct}% PACE COVERAGE</em>
    <em>MULTI-SOURCE VERIFIED</em>
    <em>SPORTSBOOK INFLUENCE 0.0%</em>
  </div>
</div>"""

    game_context = _game_context_html(display_game)
    matchup_class = " with-context" if game_context else ""
    matchup = f"""
<div class="gt168-step5-matchup{matchup_class}">
  {_team_header(identity, away, "away", display_game)}
  <div class="gt168-step5-vs">VS</div>
  {_team_header(identity, home, "home", display_game)}
  {game_context}
</div>"""

    environment = """
<section class="gt168-step5-environment" data-testid="gt168-step5-environment">
  <div class="gt168-step5-env-title"><b>▥ EXPECTED GAME ENVIRONMENT</b><span>Projected game pace and total offensive opportunities</span></div>
  <div class="gt168-step5-summary-grid">
""" + "".join(
        [
            _summary_metric("Away Drives", _num(contract.get("expected_away_drives"))),
            _summary_metric("Home Drives", _num(contract.get("expected_home_drives"))),
            _summary_metric("Combined Drives", _num(contract.get("expected_combined_drives"))),
            _summary_metric("Projected Plays", _num(contract.get("expected_combined_plays"), 0)),
            _summary_metric("Tempo Grade", _clean(contract.get("tempo_grade")) or "—"),
            _summary_metric("Pace Volatility", _clean(contract.get("pace_volatility")) or "—"),
        ]
    ) + "</div></section>"

    insights = f"""
<div class="gt168-step5-insights">
  <div class="gt168-step5-read">
    <span>MATCHUP READ</span>
    <b>{escape(_clean(contract.get("matchup_read")))}</b>
    <small>{escape(_clean(contract.get("matchup_read_detail")))}</small>
  </div>
  <div class="gt168-step5-stack">
    {_insight_card("🚀", "BIGGEST ACCELERATOR", _clean(contract.get("biggest_accelerator")), _clean(contract.get("biggest_accelerator_detail")), "accelerator")}
    {_insight_card("🛑", "BIGGEST BRAKE", _clean(contract.get("biggest_brake")), _clean(contract.get("biggest_brake_detail")), "brake")}
  </div>
  <div class="gt168-step5-stack">
    {_insight_card("▥", "O/U IMPACT", _clean(contract.get("ou_impact")), _clean(contract.get("ou_impact_detail")), "impact")}
    {_insight_card("🛡", "DATA CONFIDENCE", f"{int(contract.get('data_confidence') or 0)}%", "NCAA pace + verified drive evidence; missing supplemental fields fail closed.", "confidence")}
  </div>
</div>"""

    body = (
        header
        + matchup
        + '<div class="gt168-step5-profile-grid">'
        + _profile_html(identity, away, away_profile, "away")
        + _profile_html(identity, home, home_profile, "home")
        + "</div>"
        + environment
        + insights
        + '<div class="gt168-step5-integrity">SPORTSDATAVERSE PBP PRIMARY • NCAA MODEL FROZEN • PUNT & RALLY DRIVE EFFICIENCY • MODEL SAFE • PROJECTION MUTATION OFF</div>'
    )

    return STEP5_CSS + f"""
<details class="gt159-step gt168-step5 {state_class}" data-testid="gt157-step-5"
 data-step5-state="{escape(state)}"
 data-step5-coverage="{coverage_pct}"
 data-step5-away-pbp-delivery="{escape(away_delivery)}"
 data-step5-home-pbp-delivery="{escape(home_delivery)}"
 data-step5-away-pbp-games="{away_pbp_games}"
 data-step5-home-pbp-games="{home_pbp_games}"
 data-step5-marker="{STEP5_PRESENTATION_MARKER}"
 data-step5-data-marker="{STEP5_DATA_MARKER}"
 data-step5-visual-marker="{STEP5_VISUAL_MARKER}"
 data-step5-deployment-marker="{STEP5_DEPLOYMENT_MARKER}" open>
 <summary class="gt168-step5-summary-shell">
   <span class="gt159-num">5</span>
   <span class="gt159-stepcopy"><b>Pace & Expected Possessions</b><span>Plays • tempo • drives • no-huddle • expected opportunities</span></span>
   <span class="gt159-state {state_class}">{escape(state)}</span>
 </summary>
 <div class="gt168-step5-body">{body}</div>
</details>"""


STEP5_CSS = r"""
<style>
.gt168-step5{position:relative;border:1px solid rgba(0,222,255,.72)!important;border-left:4px solid #00e9ff!important;border-radius:16px!important;background:linear-gradient(145deg,#031420,#071321 58%,#0b1024)!important;overflow:hidden!important;box-shadow:0 0 30px rgba(0,217,255,.08)}
.gt168-step5:after{content:"";position:absolute;inset:0;pointer-events:none;border-radius:15px;background:linear-gradient(90deg,rgba(0,239,255,.09),transparent 22%,transparent 78%,rgba(151,77,255,.10))}
.gt168-step5-summary-shell{position:relative;z-index:2;grid-template-columns:32px minmax(0,1fr) auto!important;min-height:54px!important}
.gt168-step5-body{position:relative;z-index:2;padding:2px 12px 14px 12px}
.gt168-step5-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;border:1px solid rgba(30,174,255,.36);border-radius:13px;background:linear-gradient(90deg,#061b2c,#081525 58%,#0d1027)}
.gt168-step5-title{display:flex;align-items:center;gap:11px;min-width:0}.gt168-step5-title>span{width:42px;height:42px;display:grid;place-items:center;border-radius:11px;background:linear-gradient(145deg,#1172b8,#0a456d);color:white;font-weight:1000;font-size:19px;box-shadow:0 0 16px rgba(0,216,255,.24)}.gt168-step5-title b{display:block;color:#f8fbff;font-size:15px}.gt168-step5-title small{display:block;color:#9ab4c8;font-size:10px;margin-top:3px}
.gt168-step5-chips{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.gt168-step5-chips em{font-style:normal;padding:5px 8px;border-radius:999px;border:1px solid rgba(61,241,186,.52);background:rgba(8,81,65,.20);color:#58efbd;font-size:8px;font-weight:950;letter-spacing:.04em}.gt168-step5-chips em:last-child{border-color:rgba(176,103,255,.55);color:#d8b8ff;background:rgba(81,45,116,.18)}
.gt168-step5-matchup{display:grid;grid-template-columns:1fr 54px 1fr;align-items:center;gap:10px;margin-top:10px;padding:12px 14px;border:1px solid rgba(58,150,197,.28);border-radius:13px;background:#061724}.gt168-step5-matchup.with-context{grid-template-columns:1fr 54px 1fr minmax(135px,.62fr)}.gt168-step5-game-context{align-self:stretch;display:flex;flex-direction:column;justify-content:center;padding:9px 11px;border-left:1px solid rgba(71,173,235,.28);color:#dceafa}.gt168-step5-game-context b{font-size:9px;color:#b9d1e3}.gt168-step5-game-context strong{font-size:12px;margin-top:3px}.gt168-step5-game-context span{font-size:8px;color:#9fb5c6;margin-top:4px}.gt168-step5-game-context small{font-size:7px;color:#74bfe8;margin-top:3px}.gt168-step5-teamhead{display:flex;align-items:center;gap:10px}.gt168-step5-teamhead.home{flex-direction:row-reverse;text-align:right}.gt168-step5-teamhead span{display:block;color:#60d8ff;font-size:8px;font-weight:950;letter-spacing:.12em}.gt168-step5-teamhead.home span{color:#ff9b4f}.gt168-step5-teamhead b{display:block;color:#f4f8fd;font-size:17px;line-height:1.05;margin-top:2px}.gt168-step5-teamhead small{display:block;color:#8ca3b8;font-size:9px;margin-top:3px}.gt168-step5-logo,.gt168-step5-logo-fallback{width:56px;height:56px;flex:0 0 56px;object-fit:contain}.gt168-step5-logo-fallback{display:grid;place-items:center;border-radius:50%;background:#0f2c40;color:#7bd9ff;font-weight:950}.gt168-step5-vs{width:42px;height:42px;display:grid;place-items:center;border-radius:50%;border:1px solid rgba(71,173,235,.42);background:#082238;color:#91bedb;font-size:10px;font-weight:950;margin:auto}
.gt168-step5-profile-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:10px}.gt168-step5-profile{padding:10px;border:1px solid rgba(0,229,255,.42);border-left:4px solid #00e5ff;border-radius:13px;background:linear-gradient(145deg,#052132,#061724)}.gt168-step5-profile.home{border-color:rgba(255,132,63,.46);border-left-color:#ff7c3f;background:linear-gradient(145deg,#201814,#101523)}.gt168-step5-profile-title b{display:block;color:#70eaff;font-size:13px}.gt168-step5-profile.home .gt168-step5-profile-title b{color:#ffad69}.gt168-step5-profile-title span{display:block;color:#8fa5b8;font-size:9px;margin-top:2px}.gt168-step5-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:9px}.gt168-step5-metric{position:relative;min-height:112px;padding:9px;border:1px solid rgba(43,149,205,.35);border-radius:10px;background:#071b29;box-sizing:border-box}.gt168-step5-profile.home .gt168-step5-metric{border-color:rgba(207,115,48,.36);background:#151923}.gt168-step5-metric.limited{border-color:rgba(255,201,75,.35);background:rgba(78,59,12,.16)}.gt168-step5-metric-kicker{display:flex;align-items:center;gap:5px;color:#a9bdd0;font-size:8px;font-weight:900;line-height:1.2}.gt168-step5-metric-kicker i{font-style:normal;color:#53dfff;font-size:13px}.gt168-step5-profile.home .gt168-step5-metric-kicker i{color:#ff9e4d}.gt168-step5-metric strong{display:block;color:white;font-size:23px;line-height:1;margin-top:11px}.gt168-step5-metric em{display:inline-block;margin-top:8px;padding:3px 8px;border-radius:999px;border:1px solid rgba(59,237,180,.58);color:#5ff1bd;font-size:8px;font-style:normal;font-weight:950}.gt168-step5-profile.home .gt168-step5-metric em{border-color:rgba(255,183,70,.60);color:#ffc357}.gt168-step5-metric.limited em{border-color:rgba(255,206,77,.52)!important;color:#ffd358!important}.gt168-step5-metric small{display:block;color:#60798f;font-size:7px;line-height:1.25;margin-top:6px}
.gt168-step5-environment{margin-top:11px;padding:11px;border:1px solid rgba(55,203,188,.46);border-radius:13px;background:linear-gradient(90deg,#062129,#071626 70%,#0c1227)}.gt168-step5-env-title b{display:block;color:#f1f8fd;font-size:13px}.gt168-step5-env-title span{display:block;color:#8ba4b8;font-size:9px;margin-top:2px}.gt168-step5-summary-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));margin-top:9px;border:1px solid rgba(70,150,192,.22);border-radius:10px;overflow:hidden}.gt168-step5-summary-metric{padding:9px 7px;text-align:center;border-right:1px solid rgba(70,150,192,.18);background:rgba(5,22,34,.56)}.gt168-step5-summary-metric:last-child{border-right:0}.gt168-step5-summary-metric span{display:block;color:#9eb0c0;font-size:8px}.gt168-step5-summary-metric b{display:block;color:#f7fbff;font-size:20px;margin-top:4px}.gt168-step5-summary-metric small{display:block;color:#6fe7ba;font-size:7px;margin-top:3px}
.gt168-step5-insights{display:grid;grid-template-columns:1.08fr 1fr 1fr;gap:8px;margin-top:10px}.gt168-step5-read,.gt168-step5-insight{border:1px solid rgba(56,178,229,.42);border-radius:11px;background:#071d2c;padding:11px;box-sizing:border-box}.gt168-step5-read{border-left:4px solid #45efb1}.gt168-step5-read span,.gt168-step5-insight span{display:block;color:#89bddf;font-size:8px;font-weight:950;letter-spacing:.06em}.gt168-step5-read b,.gt168-step5-insight b{display:block;color:#5aefbd;font-size:12px;line-height:1.25;margin-top:7px}.gt168-step5-read small,.gt168-step5-insight small{display:block;color:#b3c4d2;font-size:9px;line-height:1.45;margin-top:7px}.gt168-step5-stack{display:grid;gap:8px}.gt168-step5-insight{display:grid;grid-template-columns:32px minmax(0,1fr);gap:8px;padding:9px}.gt168-step5-insight-icon{width:32px;height:32px;display:grid;place-items:center;border-radius:9px;background:rgba(35,134,183,.19);font-size:16px}.gt168-step5-insight.brake{border-color:rgba(255,89,101,.50)}.gt168-step5-insight.brake span,.gt168-step5-insight.brake b{color:#ff7e88}.gt168-step5-insight.impact b,.gt168-step5-insight.confidence b{color:#57efb8}.gt168-step5-integrity{margin-top:10px;padding:7px 9px;border:1px solid rgba(89,152,190,.20);border-radius:9px;background:#06131e;color:#7f9bb1;font-size:8px;text-align:center;font-weight:850;letter-spacing:.035em}
@media(max-width:760px){.gt168-step5-head{align-items:flex-start;flex-direction:column}.gt168-step5-chips{justify-content:flex-start}.gt168-step5-profile-grid{grid-template-columns:1fr}.gt168-step5-insights{grid-template-columns:1fr}.gt168-step5-summary-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.gt168-step5-summary-metric:nth-child(3){border-right:0}.gt168-step5-matchup,.gt168-step5-matchup.with-context{grid-template-columns:1fr 40px 1fr}.gt168-step5-game-context{grid-column:1/-1;border-left:0;border-top:1px solid rgba(71,173,235,.28);padding:8px 2px 0}.gt168-step5-teamhead b{font-size:13px}.gt168-step5-logo,.gt168-step5-logo-fallback{width:46px;height:46px;flex-basis:46px}}
@media(max-width:420px){.gt168-step5-body{padding:2px 7px 10px}.gt168-step5-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.gt168-step5-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt168-step5-matchup{padding:8px}.gt168-step5-teamhead{gap:5px}.gt168-step5-teamhead small{display:none}.gt168-step5-metric{min-height:105px}.gt168-step5-title b{font-size:12px}.gt168-step5-title small{font-size:8px}}
</style>
"""


__all__ = [
    "ESPN_SUMMARY_URL",
    "SPORTSDATAVERSE_GAME_URL",
    "FROZEN_PREDECESSOR",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP5_CSS",
    "STEP5_DATA_MARKER",
    "STEP5_DEPLOYMENT_MARKER",
    "STEP5_PRESENTATION_MARKER",
    "STEP5_VISUAL_MARKER",
    "_parse_drive_evidence",
    "_parse_sportsdataverse_evidence",
    "build_step5_contract",
    "render_step5_html",
]
