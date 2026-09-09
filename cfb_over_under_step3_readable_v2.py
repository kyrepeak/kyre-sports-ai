"""CFB O/U Step 3 V2 — readable current offense-vs-defense evidence.

Purpose
-------
Replace developer-facing Step-3 numbers with football information people can
actually read:

- points per game vs points allowed per game,
- total yards per game vs total yards allowed per game,
- passing yards per game vs passing yards allowed per game,
- rushing yards per game vs rushing yards allowed per game,
- passing TDs per game vs passing TDs allowed per game,
- rushing TDs per game vs rushing TDs allowed per game,
- first downs per game vs first downs allowed per game,
- yards per play vs yards per play allowed.

The page shows BOTH directions:
1. away offense vs home defense,
2. home offense vs away defense.

Data hierarchy
--------------
1. Checked-in Step-3 current snapshot for stable Streamlit rendering.
2. ESPN Core current-season team statistics for offense.
3. ESPN exact-event summaries for defense-allowed aggregation.
4. Existing certified team schedule parser for completed-game identity/cutoff.

The new evidence panel is descriptive/readable only in this upgrade. It does
NOT add a new projection formula or sportsbook/market input. The existing
certified model math remains unchanged while we validate raw-stat calibration
and opponent-strength treatment.

Important quality rule
----------------------
A one- or two-game early-season sample may be displayed because it is factual,
but it is explicitly labeled EARLY SAMPLE and receives 0% new projection
weight from this V2 readable layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from statistics import fmean
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_deep_data_reconciliation_v1 as deep

MODEL_VERSION = "CFB O/U STEP 3 V2 • READABLE OFFENSE VS DEFENSE"
SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "data" / "cfb_step3_matchup_stats_v1.json"
)
NEW_PROJECTION_WEIGHT = 0.0
SPORTSBOOK_INPUT_USED = False
MARKET_PROBABILITY_USED = False
EDGE_OR_EV_USED = False
MONTE_CARLO_USED = False

_METRICS = (
    {
        "key": "points",
        "label": "Points",
        "offense": "points_pg",
        "defense": "points_allowed_pg",
        "offense_suffix": "PPG",
        "defense_suffix": "allowed",
    },
    {
        "key": "total_yards",
        "label": "Total yards",
        "offense": "total_yards_pg",
        "defense": "total_yards_allowed_pg",
        "offense_suffix": "YPG",
        "defense_suffix": "allowed",
    },
    {
        "key": "pass_yards",
        "label": "Passing yards",
        "offense": "pass_yards_pg",
        "defense": "pass_yards_allowed_pg",
        "offense_suffix": "YPG",
        "defense_suffix": "allowed",
    },
    {
        "key": "rush_yards",
        "label": "Rushing yards",
        "offense": "rush_yards_pg",
        "defense": "rush_yards_allowed_pg",
        "offense_suffix": "YPG",
        "defense_suffix": "allowed",
    },
    {
        "key": "pass_td",
        "label": "Passing TDs",
        "offense": "pass_td_pg",
        "defense": "pass_td_allowed_pg",
        "offense_suffix": "/ game",
        "defense_suffix": "allowed / game",
    },
    {
        "key": "rush_td",
        "label": "Rushing TDs",
        "offense": "rush_td_pg",
        "defense": "rush_td_allowed_pg",
        "offense_suffix": "/ game",
        "defense_suffix": "allowed / game",
    },
    {
        "key": "first_downs",
        "label": "First downs",
        "offense": "first_downs_pg",
        "defense": "first_downs_allowed_pg",
        "offense_suffix": "/ game",
        "defense_suffix": "allowed / game",
    },
    {
        "key": "yards_per_play",
        "label": "Yards / play",
        "offense": "yards_per_play",
        "defense": "yards_per_play_allowed",
        "offense_suffix": "YPP",
        "defense_suffix": "allowed",
    },
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except Exception:
        return None


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def _snapshot_payload() -> dict[str, Any]:
    try:
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _snapshot_team(team_id: str) -> dict[str, Any]:
    payload = _snapshot_payload()
    teams = payload.get("teams") or {}
    row = teams.get(_clean(team_id)) if isinstance(teams, Mapping) else None
    return dict(row) if isinstance(row, Mapping) else {}


def _flatten_core_stats(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    splits = payload.get("splits") or {}
    if not isinstance(splits, Mapping):
        return out
    for category in splits.get("categories") or []:
        if not isinstance(category, Mapping):
            continue
        category_name = _clean(category.get("name"))
        for stat in category.get("stats") or []:
            if not isinstance(stat, Mapping):
                continue
            name = _clean(stat.get("name"))
            if not name:
                continue
            out[name] = {
                "category": category_name,
                "value": _float(stat.get("value")),
                "display_value": _clean(stat.get("displayValue")),
                "rank": _int(stat.get("rank")),
                "display_name": _clean(stat.get("displayName")),
            }
    return out


def _stat_value(
    stats: Mapping[str, Mapping[str, Any]],
    name: str,
) -> float | None:
    row = stats.get(name) or {}
    return _float(row.get("value")) if isinstance(row, Mapping) else None


@st.cache_data(ttl=900, show_spinner=False)
def _live_offense(
    team_id: str,
    season: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    team_id = _clean(team_id)
    if not team_id.isdigit():
        return {}, {"ready": False, "reason": "missing numeric ESPN team ID"}

    url = (
        f"{deep._CORE_ROOT}/seasons/{int(season)}/types/2/"
        f"teams/{team_id}/statistics?lang=en&region=us"
    )
    payload, attempts = deep._core_json(
        url,
        f"ESPN Core CFB team {team_id} current-season statistics",
    )
    stats = _flatten_core_stats(payload)
    games = _int(_stat_value(stats, "gamesPlayed"))
    if games is None:
        games = _int(_stat_value(stats, "teamGamesPlayed"))
    games = max(0, int(games or 0))
    if not stats or games <= 0:
        return {}, {
            "ready": False,
            "games": games,
            "attempts": attempts,
            "reason": "ESPN Core season stats unavailable",
        }

    total_points = _stat_value(stats, "totalPoints")
    total_yards = (
        _stat_value(stats, "netTotalYards")
        or _stat_value(stats, "totalYards")
    )
    pass_yards = (
        _stat_value(stats, "netPassingYards")
        or _stat_value(stats, "passingYards")
    )
    rush_yards = _stat_value(stats, "rushingYards")
    pass_td = _stat_value(stats, "passingTouchdowns")
    rush_td = _stat_value(stats, "rushingTouchdowns")
    first_downs = _stat_value(stats, "firstDowns")
    plays = _stat_value(stats, "totalOffensivePlays")

    def per_game(total: float | None) -> float | None:
        return float(total) / games if total is not None and games else None

    offense = {
        "games": games,
        "points_pg": (
            _stat_value(stats, "totalPointsPerGame")
            if _stat_value(stats, "totalPointsPerGame") is not None
            else per_game(total_points)
        ),
        "total_yards_pg": (
            _stat_value(stats, "netYardsPerGame")
            if _stat_value(stats, "netYardsPerGame") is not None
            else per_game(total_yards)
        ),
        "pass_yards_pg": (
            _stat_value(stats, "netPassingYardsPerGame")
            if _stat_value(stats, "netPassingYardsPerGame") is not None
            else per_game(pass_yards)
        ),
        "rush_yards_pg": (
            _stat_value(stats, "rushingYardsPerGame")
            if _stat_value(stats, "rushingYardsPerGame") is not None
            else per_game(rush_yards)
        ),
        "pass_td_pg": per_game(pass_td),
        "rush_td_pg": per_game(rush_td),
        # ESPN's 2026 firstDownsPerGame field is currently scaled by 100
        # (e.g. 2700.00 for 27 first downs in one game), so derive it.
        "first_downs_pg": per_game(first_downs),
        "yards_per_play": (
            float(total_yards) / float(plays)
            if total_yards is not None and plays not in (None, 0)
            else None
        ),
    }
    return offense, {
        "ready": True,
        "games": games,
        "provider": "ESPN Core current-season team statistics",
        "attempts": attempts,
    }


def _team_block_stats(
    summary: Mapping[str, Any],
    team_id: str,
) -> dict[str, Any]:
    box = summary.get("boxscore") or {}
    if not isinstance(box, Mapping):
        return {}
    wanted = _clean(team_id)
    for block in box.get("teams") or []:
        if not isinstance(block, Mapping):
            continue
        team = block.get("team") or {}
        if not isinstance(team, Mapping):
            team = {}
        if _clean(team.get("id")) != wanted:
            continue
        out: dict[str, Any] = {}
        for stat in block.get("statistics") or []:
            if not isinstance(stat, Mapping):
                continue
            name = _clean(stat.get("name") or stat.get("label"))
            if name:
                out[name] = stat.get("displayValue")
        return out
    return {}


def _opponent_team_id(
    summary: Mapping[str, Any],
    team_id: str,
) -> str:
    box = summary.get("boxscore") or {}
    wanted = _clean(team_id)
    for block in box.get("teams") or [] if isinstance(box, Mapping) else []:
        if not isinstance(block, Mapping):
            continue
        team = block.get("team") or {}
        if not isinstance(team, Mapping):
            team = {}
        tid = _clean(team.get("id"))
        if tid and tid != wanted:
            return tid
    return ""


def _parse_comp_attempt(value: Any) -> tuple[int | None, int | None]:
    text = _clean(value)
    if "/" not in text:
        return None, None
    left, right = text.split("/", 1)
    return _int(left), _int(right)


def _player_category_td(
    summary: Mapping[str, Any],
    team_id: str,
    category_name: str,
) -> float | None:
    box = summary.get("boxscore") or {}
    wanted = _clean(team_id)
    for pblock in box.get("players") or [] if isinstance(box, Mapping) else []:
        if not isinstance(pblock, Mapping):
            continue
        team = pblock.get("team") or {}
        if not isinstance(team, Mapping):
            team = {}
        if _clean(team.get("id")) != wanted:
            continue
        for category in pblock.get("statistics") or []:
            if not isinstance(category, Mapping):
                continue
            if _clean(category.get("name")).lower() != category_name.lower():
                continue
            labels = [
                _clean(label).upper()
                for label in category.get("labels") or []
            ]
            try:
                td_idx = labels.index("TD")
            except ValueError:
                return None
            total = 0.0
            found = False
            for athlete in category.get("athletes") or []:
                if not isinstance(athlete, Mapping):
                    continue
                stats = athlete.get("stats") or []
                if td_idx >= len(stats):
                    continue
                value = _float(stats[td_idx])
                if value is None:
                    continue
                total += value
                found = True
            return total if found else 0.0
    return None


def _completed_rows(
    team_id: str,
    season: int,
    cutoff: datetime,
    excluded_event_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Completed current-season games without Step-11 opponent hydration."""
    payload, attempts = deep.history_engine._fetch_team_schedule(
        _clean(team_id),
        int(season),
    )
    rows: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        row = deep.form_engine._event_row_with_opponent_record(
            event,
            _clean(team_id),
        )
        if not row:
            continue
        event_id = _clean(row.get("event_id"))
        if excluded_event_id and event_id == _clean(excluded_event_id):
            continue
        dt = row.get("date_dt")
        if not isinstance(dt, datetime):
            continue
        if dt >= cutoff or dt.year != int(season):
            continue
        comps = event.get("competitions") or []
        comp = comps[0] if comps and isinstance(comps[0], Mapping) else {}
        item = dict(row)
        if comp.get("neutralSite") is True:
            item["location"] = "neutral"
        else:
            item["location"] = _clean(item.get("home_away")).lower()
        rows.append(item)
    rows.sort(
        key=lambda row: row.get("date_dt")
        or datetime.min.replace(tzinfo=timezone.utc)
    )
    return rows, attempts


@st.cache_data(ttl=900, show_spinner=False)
def _live_defense(
    team_id: str,
    season: int,
    cutoff_iso: str,
    excluded_event_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cutoff = _parse_dt(cutoff_iso) or datetime.max.replace(tzinfo=timezone.utc)
    rows, attempts = _completed_rows(
        _clean(team_id),
        int(season),
        cutoff,
        _clean(excluded_event_id),
    )
    if not rows:
        return {}, {
            "ready": False,
            "games": 0,
            "summary_games": 0,
            "attempts": attempts,
            "reason": "no completed current-season games before kickoff",
        }

    totals = {
        "points": 0.0,
        "total_yards": 0.0,
        "pass_yards": 0.0,
        "rush_yards": 0.0,
        "pass_td": 0.0,
        "rush_td": 0.0,
        "first_downs": 0.0,
        "plays": 0.0,
    }
    summary_games = 0
    event_rows: list[dict[str, Any]] = []

    for row in rows:
        event_id = _clean(row.get("event_id"))
        if not event_id:
            continue
        summary, summary_attempts = deep.environment_engine._fetch_summary(
            event_id
        )
        attempts.extend(summary_attempts or [])
        opponent_id = _opponent_team_id(summary, team_id)
        opp = _team_block_stats(summary, opponent_id) if opponent_id else {}
        if not opp:
            continue

        total_yards = _float(opp.get("totalYards"))
        pass_yards = _float(opp.get("netPassingYards"))
        rush_yards = _float(opp.get("rushingYards"))
        first_downs = _float(opp.get("firstDowns"))
        rush_attempts = _float(opp.get("rushingAttempts"))
        _, pass_attempts = _parse_comp_attempt(opp.get("completionAttempts"))
        pass_td = _player_category_td(summary, opponent_id, "passing")
        rush_td = _player_category_td(summary, opponent_id, "rushing")
        points = _float(row.get("points_against"))

        required = (
            total_yards,
            pass_yards,
            rush_yards,
            first_downs,
            points,
        )
        if any(value is None for value in required):
            continue

        plays = float(rush_attempts or 0.0) + float(pass_attempts or 0.0)
        totals["points"] += float(points)
        totals["total_yards"] += float(total_yards)
        totals["pass_yards"] += float(pass_yards)
        totals["rush_yards"] += float(rush_yards)
        totals["pass_td"] += float(pass_td or 0.0)
        totals["rush_td"] += float(rush_td or 0.0)
        totals["first_downs"] += float(first_downs)
        totals["plays"] += plays
        summary_games += 1
        event_rows.append({
            "event_id": event_id,
            "opponent_id": opponent_id,
            "opponent": _clean(row.get("opponent_name")),
            "points_allowed": float(points),
            "total_yards_allowed": float(total_yards),
            "pass_yards_allowed": float(pass_yards),
            "rush_yards_allowed": float(rush_yards),
            "pass_td_allowed": float(pass_td or 0.0),
            "rush_td_allowed": float(rush_td or 0.0),
            "first_downs_allowed": float(first_downs),
            "plays": plays,
        })

    if summary_games <= 0:
        return {}, {
            "ready": False,
            "games": len(rows),
            "summary_games": 0,
            "attempts": attempts,
            "reason": "completed games exist but exact box-score summaries were unavailable",
        }

    defense = {
        "games": summary_games,
        "points_allowed_pg": totals["points"] / summary_games,
        "total_yards_allowed_pg": totals["total_yards"] / summary_games,
        "pass_yards_allowed_pg": totals["pass_yards"] / summary_games,
        "rush_yards_allowed_pg": totals["rush_yards"] / summary_games,
        "pass_td_allowed_pg": totals["pass_td"] / summary_games,
        "rush_td_allowed_pg": totals["rush_td"] / summary_games,
        "first_downs_allowed_pg": totals["first_downs"] / summary_games,
        "yards_per_play_allowed": (
            totals["total_yards"] / totals["plays"]
            if totals["plays"] > 0
            else None
        ),
    }
    return defense, {
        "ready": True,
        "games": len(rows),
        "summary_games": summary_games,
        "coverage": summary_games / len(rows) if rows else 0.0,
        "provider": "ESPN exact-event completed-game summaries",
        "events": event_rows,
        "attempts": attempts,
    }


def _merge_non_null(
    primary: Mapping[str, Any],
    fallback: Mapping[str, Any],
) -> dict[str, Any]:
    keys = set(primary) | set(fallback)
    out: dict[str, Any] = {}
    for key in keys:
        value = primary.get(key)
        if value is None:
            value = fallback.get(key)
        out[key] = value
    return out


def _cutoff_iso(game: Mapping[str, Any]) -> str:
    cutoff = deep._cutoff(game)
    return cutoff.astimezone(timezone.utc).isoformat()


@st.cache_data(ttl=600, show_spinner=False)
def load_team_step3(
    team_id: str,
    team_name: str,
    season: int,
    cutoff_iso: str,
    excluded_event_id: str,
) -> dict[str, Any]:
    snapshot = _snapshot_team(team_id)
    snapshot_offense = dict(snapshot.get("offense") or {})
    snapshot_defense = dict(snapshot.get("defense") or {})

    live_offense, offense_diag = _live_offense(team_id, season)
    live_defense, defense_diag = _live_defense(
        team_id,
        season,
        cutoff_iso,
        excluded_event_id,
    )

    # Prefer live current data when it is available, but retain the checked-in
    # snapshot as a field-level fallback for deployed runtimes.
    offense = _merge_non_null(live_offense, snapshot_offense)
    defense = _merge_non_null(live_defense, snapshot_defense)

    games = max(
        int(offense.get("games") or 0),
        int(defense.get("games") or 0),
        int(snapshot.get("games") or 0),
    )
    snapshot_used = bool(snapshot) and (
        not offense_diag.get("ready")
        or not defense_diag.get("ready")
        or any(
            live_offense.get(key) is None and snapshot_offense.get(key) is not None
            for key in snapshot_offense
        )
        or any(
            live_defense.get(key) is None and snapshot_defense.get(key) is not None
            for key in snapshot_defense
        )
    )
    return {
        "version": MODEL_VERSION,
        "team_id": _clean(team_id),
        "team": _clean(team_name) or _clean(snapshot.get("team")) or "Team",
        "games": games,
        "offense": offense,
        "defense": defense,
        "display_ready": bool(offense and defense and games > 0),
        "snapshot_used": snapshot_used,
        "source": (
            "ESPN Core season offense + ESPN exact-event defense summaries"
            + (" + checked-in fallback" if snapshot_used else "")
        ),
        "offense_diagnostics": offense_diag,
        "defense_diagnostics": defense_diag,
    }


def _sample_label(games: int) -> str:
    if games <= 0:
        return "NO CURRENT SAMPLE"
    if games == 1:
        return "VERY EARLY • 1 GAME"
    if games == 2:
        return "EARLY • 2 GAMES"
    if games == 3:
        return "BUILDING • 3 GAMES"
    return f"CURRENT • {games} GAMES"


def _comparison(
    offense_value: float | None,
    defense_value: float | None,
) -> tuple[float | None, str, str]:
    """Describe production relative to current opponent allowance.

    This is deliberately NOT called an edge. With tiny early-season samples
    and cross-division matchups, raw values alone cannot establish true team
    strength.
    """
    if offense_value is None or defense_value is None:
        return None, "DATA CHECK", "neutral"
    delta = float(offense_value) - float(defense_value)
    scale = max(abs(float(defense_value)), 1.0)
    ratio = delta / scale
    if ratio >= 0.25:
        return delta, "ABOVE CURRENT ALLOWANCE", "above-strong"
    if ratio >= 0.10:
        return delta, "SLIGHTLY ABOVE ALLOWANCE", "above"
    if ratio <= -0.25:
        return delta, "BELOW CURRENT ALLOWANCE", "below-strong"
    if ratio <= -0.10:
        return delta, "SLIGHTLY BELOW ALLOWANCE", "below"
    return delta, "NEAR CURRENT ALLOWANCE", "neutral"


def _battle(
    offense_team: Mapping[str, Any],
    defense_team: Mapping[str, Any],
) -> dict[str, Any]:
    offense_name = _clean(offense_team.get("team")) or "Offense"
    defense_name = _clean(defense_team.get("team")) or "Defense"
    offense = offense_team.get("offense") or {}
    defense = defense_team.get("defense") or {}

    rows: list[dict[str, Any]] = []
    above = below = 0
    for metric in _METRICS:
        off = _float(offense.get(metric["offense"]))
        allowed = _float(defense.get(metric["defense"]))
        delta, label, cls = _comparison(off, allowed)
        if cls.startswith("above"):
            above += 1
        elif cls.startswith("below"):
            below += 1
        rows.append({
            **metric,
            "offense_value": off,
            "defense_value": allowed,
            "difference": delta,
            "comparison_label": label,
            "comparison_class": cls,
        })

    if above >= below + 2:
        summary = (
            f"{offense_name} is above {defense_name}'s current allowance "
            f"in {above} of {len(rows)} displayed categories"
        )
        summary_class = "above"
    elif below >= above + 2:
        summary = (
            f"{offense_name} is below {defense_name}'s current allowance "
            f"in {below} of {len(rows)} displayed categories"
        )
        summary_class = "below"
    else:
        summary = "Production vs allowance is mixed across the displayed categories"
        summary_class = "neutral"

    return {
        "offense_team": offense_name,
        "defense_team": defense_name,
        "offense_games": int(offense_team.get("games") or 0),
        "defense_games": int(defense_team.get("games") or 0),
        "offense_sample": _sample_label(int(offense_team.get("games") or 0)),
        "defense_sample": _sample_label(int(defense_team.get("games") or 0)),
        "rows": rows,
        "above_allowance": above,
        "below_allowance": below,
        "summary": summary,
        "summary_class": summary_class,
    }


def build_matchup_step3(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    season = deep._season(game)
    cutoff_iso = _cutoff_iso(game)
    excluded_event_id = _clean(game.get("espn_event_id"))

    away_id = _clean(
        away.get("espn_team_id")
        or game.get("away_espn_team_id")
    )
    home_id = _clean(
        home.get("espn_team_id")
        or game.get("home_espn_team_id")
    )

    away_team = load_team_step3(
        away_id,
        _clean(away.get("team") or game.get("away_team")),
        season,
        cutoff_iso,
        excluded_event_id,
    )
    home_team = load_team_step3(
        home_id,
        _clean(home.get("team") or game.get("home_team")),
        season,
        cutoff_iso,
        excluded_event_id,
    )

    display_ready = bool(
        away_team.get("display_ready")
        and home_team.get("display_ready")
    )
    min_games = min(
        int(away_team.get("games") or 0),
        int(home_team.get("games") or 0),
    )
    sample_state = _sample_label(min_games)

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "display_ready": display_ready,
        "model_ready": False,
        "reason": (
            "Readable raw matchup evidence is active. New projection weight "
            "remains 0% until early-season sample and opponent-strength "
            "calibration are separately certified."
        ),
        "projection_weight": NEW_PROJECTION_WEIGHT,
        "sample_state": sample_state,
        "away_team": away_team,
        "home_team": home_team,
        "away_offense_vs_home_defense": _battle(away_team, home_team),
        "home_offense_vs_away_defense": _battle(home_team, away_team),
        "sources": [
            "ESPN Core current-season team statistics",
            "ESPN exact-event completed-game summaries",
            "checked-in certified Step-3 current snapshot fallback",
        ],
        "sportsbook_input_used": SPORTSBOOK_INPUT_USED,
        "market_probability_used": MARKET_PROBABILITY_USED,
        "edge_or_ev_used": EDGE_OR_EV_USED,
        "monte_carlo_used": MONTE_CARLO_USED,
    }


def clear_step3_cache() -> None:
    for fn in (
        _snapshot_payload,
        _live_offense,
        _live_defense,
        load_team_step3,
    ):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "MODEL_VERSION",
    "NEW_PROJECTION_WEIGHT",
    "SNAPSHOT_PATH",
    "_METRICS",
    "_battle",
    "_comparison",
    "_completed_rows",
    "_live_defense",
    "_live_offense",
    "build_matchup_step3",
    "clear_step3_cache",
    "load_team_step3",
]
