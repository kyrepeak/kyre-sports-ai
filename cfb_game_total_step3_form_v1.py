"""Universal presentation-only Step 3 Current Form & Opponent Quality.

Step 3 answers one question for every future CFB Game Total matchup:
"Who is playing better lately, and how trustworthy is that form given the
quality of opponents faced?"

This module is display-only. It consumes already-reconciled evidence and never
changes projection, distribution, qualification, ranking, sportsbook, API, or
model behavior.
"""
from __future__ import annotations

from datetime import date, timedelta
from html import escape
import json
import re
from pathlib import Path
from statistics import fmean
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_deep_data_reconciliation_v1 as deep
import cfb_schedule_v1 as ncaa_schedule
import cfb_schedule_v2 as ncaa_schedule_v2
import cfb_team_data_v1 as ncaa_team_data
import cfb_team_data_v2 as ncaa_team_data_v2

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

STEP3_PRESENTATION_MARKER = "CFB_GAME_TOTAL_STEP3_CURRENT_FORM_OPPONENT_QUALITY_ACTIVE"
STEP3_MIN_OPPONENT_QUALITY_COVERAGE = 0.60
STEP3_RUNTIME_SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "cfb_runtime_snapshot_v2.json"

STEP3_REQUIRED_FIELDS = (
    "team",
    "sample_games",
    "last5_record",
    "recent_ppg",
    "recent_allowed_pg",
    "recent_diff_pg",
)

STEP3_ADVANCED_FIELDS = (
    "avg_opponent_win_pct",
    "sos_coverage",
    "avg_opponent_def_rank",
    "top40_defenses_faced",
    "record_vs_winning_teams",
    "strength_of_schedule_rank",
)

_UNAVAILABLE = {
    "",
    "—",
    "-",
    "none",
    "n/a",
    "na",
    "unavailable",
    "data limited",
}

STEP3_CSS = r"""
<style>
.gt168-step3{grid-column:1/-1!important;position:relative;border:1px solid rgba(224,65,255,.72)!important;border-radius:17px!important;background:linear-gradient(145deg,#071327 0%,#08182e 50%,#111027 100%)!important;box-shadow:0 0 0 2px rgba(112,69,255,.18),0 0 28px rgba(210,45,255,.14),0 0 42px rgba(0,214,255,.08)!important;overflow:hidden}
.gt168-step3:before{content:"";position:absolute;inset:-2px;z-index:0;border-radius:18px;padding:2px;background:linear-gradient(90deg,#ff33d2,#7d4dff,#00dcff,#37ffb0,#ffc84a,#ff496f);-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
.gt168-step3 summary,.gt168-body{position:relative;z-index:1}.gt168-step3 summary{min-height:62px!important;padding:10px 13px!important;grid-template-columns:44px minmax(0,1fr) auto!important;gap:11px!important;background:linear-gradient(90deg,rgba(36,9,57,.92),rgba(8,25,47,.90))!important}
.gt168-step3 .gt159-num{width:44px!important;height:44px!important;border-radius:11px!important;background:linear-gradient(145deg,#ff3acb,#784dff 55%,#2de9ff)!important;color:#fff!important;box-shadow:0 0 18px rgba(214,61,255,.4)!important;font-size:17px!important}
.gt168-step3 .gt159-stepcopy b{font-size:15px!important;color:#fff!important}.gt168-step3 .gt159-stepcopy span{font-size:8px!important;color:#b8a9ca!important;margin-top:4px!important}
.gt168-body{padding:11px 12px 13px}.gt168-grid{display:grid;grid-template-columns:minmax(0,1fr) 220px minmax(0,1fr);gap:8px;align-items:start}
.gt168-team{min-width:0;border:1px solid rgba(59,207,255,.30);border-radius:11px;background:linear-gradient(145deg,rgba(4,26,48,.96),rgba(7,23,42,.98));overflow:hidden}.gt168-team.home{border-color:rgba(255,80,122,.34)}
.gt168-head{display:grid;grid-template-columns:58px minmax(0,1fr) auto;gap:8px;align-items:center;padding:9px;border-bottom:1px solid rgba(75,151,195,.18)}.gt168-logo{width:54px;height:44px;object-fit:contain}.gt168-name b{display:block;color:#fff;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt168-name span{display:block;color:#8199ad;font-size:7px;margin-top:3px}.gt168-form-record{text-align:center}.gt168-form-record b{display:block;color:#60f6bf;font-size:15px}.gt168-team.home .gt168-form-record b{color:#ff6c82}.gt168-form-record span{display:block;color:#8ea2b3;font-size:6px;text-transform:uppercase}
.gt168-table-wrap{padding:8px}.gt168-table-title{color:#d9e8f2;font-size:8px;font-weight:900;margin-bottom:5px}.gt168-table{width:100%;border-collapse:collapse;font-size:6.5px}.gt168-table th{color:#7f98ac;text-align:left;padding:4px;border-bottom:1px solid rgba(86,147,185,.20);font-weight:800}.gt168-table td{padding:4px;border-bottom:1px solid rgba(61,118,153,.13);color:#d4e2ec}.gt168-table td.result.win{color:#46efb2;font-weight:900}.gt168-table td.result.loss{color:#ff6c7f;font-weight:900}.gt168-table td.result.tie{color:#ffd35c;font-weight:900}
.gt168-recent{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;padding:0 8px 8px}.gt168-metric{padding:7px 4px;border:1px solid rgba(58,143,190,.25);border-radius:8px;background:rgba(7,35,57,.78);text-align:center}.gt168-metric b{display:block;color:#eef8ff;font-size:11px}.gt168-metric span{display:block;color:#7f99ad;font-size:6px;margin-top:3px;text-transform:uppercase}.gt168-metric.good b{color:#54efb8}.gt168-metric.bad b{color:#ff6c7b}
.gt168-opp{margin:0 8px 8px;padding:8px;border:1px solid rgba(80,193,255,.30);border-radius:9px;background:rgba(3,36,60,.66)}.gt168-opp-title{display:flex;justify-content:space-between;gap:8px;color:#6de1ff;font-size:8px;font-weight:950}.gt168-opp-row{display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid rgba(77,132,164,.14);font-size:6.8px}.gt168-opp-row:last-child{border-bottom:0}.gt168-opp-row span{color:#8da5b7}.gt168-opp-row b{color:#eef6fb;text-align:right}.gt168-missing{padding:0 8px 8px;color:#f2c75d;font-size:6.5px;line-height:1.35}
.gt168-center{display:grid;gap:7px}.gt168-center-card{border:1px solid rgba(151,79,255,.36);border-radius:10px;background:linear-gradient(145deg,rgba(27,16,55,.88),rgba(8,28,50,.91));padding:8px}.gt168-center-title{text-align:center;color:#e3d4ff;font-size:8px;font-weight:950;letter-spacing:.04em}.gt168-compare-row{display:grid;grid-template-columns:1fr 1.15fr 1fr;gap:5px;align-items:center;padding:5px 0;border-bottom:1px solid rgba(114,100,168,.17);font-size:7px}.gt168-compare-row:last-child{border-bottom:0}.gt168-compare-row b:first-child{color:#5cf0bb;text-align:right}.gt168-compare-row b:last-child{color:#ff6d82}.gt168-compare-row span{color:#95a8b9;text-align:center}
.gt168-trends{display:grid;grid-template-columns:1fr 1fr;gap:6px}.gt168-trend{padding:8px;border-radius:9px;background:rgba(6,57,48,.35);border:1px solid rgba(75,244,187,.31);text-align:center}.gt168-trend.bad{background:rgba(79,17,34,.31);border-color:rgba(255,91,115,.32)}.gt168-trend b{display:block;color:#56eeb8;font-size:9px}.gt168-trend.bad b{color:#ff6d83}.gt168-trend span{display:block;color:#91a6b8;font-size:6px;margin-top:2px}
.gt168-takeaways{padding:8px}.gt168-takeaways h4{margin:0 0 6px;color:#ffd65d;font-size:8px}.gt168-takeaways div{color:#bdd0de;font-size:6.7px;line-height:1.45;margin:3px 0}.gt168-takeaways div:before{content:"✓";color:#63f3b5;margin-right:5px;font-weight:900}
.gt168-edge{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:8px;align-items:center;margin-top:8px;padding:8px 10px;border:1px solid rgba(225,63,255,.50);border-radius:9px;background:linear-gradient(90deg,rgba(81,11,104,.28),rgba(6,31,53,.88));}.gt168-edge strong{color:#ff75eb;font-size:8px}.gt168-edge span{color:#e9eef5;font-size:8px;font-weight:900}.gt168-edge small{color:#9db1c1;font-size:6.5px;text-align:right}
@media(max-width:920px){.gt168-grid{grid-template-columns:1fr}.gt168-center{order:3}.gt168-center-card{max-width:none}}
@media(max-width:520px){.gt168-head{grid-template-columns:46px minmax(0,1fr) auto}.gt168-logo{width:44px;height:38px}.gt168-table{font-size:6px}.gt168-edge{grid-template-columns:1fr}.gt168-edge small{text-align:left}}
</style>
"""


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _usable(value: Any) -> bool:
    text = _clean(value)
    return bool(text) and text.casefold() not in _UNAVAILABLE


def _float(value: Any) -> float | None:
    if value is None:
        return None
    text = _clean(value).replace(",", "").replace("%", "")
    if not text or text.casefold() in _UNAVAILABLE:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _int(value: Any) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _parse_score(value: Any) -> tuple[float | None, float | None]:
    text = _clean(value)
    match = re.search(r"(\d+)\s*[-–]\s*(\d+)", text)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def _normalize_game(row: Mapping[str, Any]) -> dict[str, Any]:
    points_for = _float(row.get("points_for"))
    points_against = _float(row.get("points_against"))
    if points_for is None or points_against is None:
        score_for, score_against = _parse_score(row.get("score"))
        if points_for is None:
            points_for = score_for
        if points_against is None:
            points_against = score_against

    result = _clean(row.get("result")).upper()[:1]
    if result not in {"W", "L", "T"} and points_for is not None and points_against is not None:
        result = "W" if points_for > points_against else "L" if points_for < points_against else "T"

    opp_pct = _float(
        row.get("opponent_record_pct")
        or row.get("opponent_win_pct")
        or row.get("opp_win_pct")
    )
    if opp_pct is not None and opp_pct > 1:
        opp_pct /= 100.0

    opp_def_rank = _int(
        row.get("opponent_def_rank")
        or row.get("opponent_defense_rank")
        or row.get("opp_def_rank")
    )
    return {
        "date": _clean(row.get("date")) or "—",
        "opponent": _clean(row.get("opponent")) or "Opponent unavailable",
        "result": result or "—",
        "points_for": points_for,
        "points_against": points_against,
        "opponent_win_pct": opp_pct,
        "opponent_def_rank": opp_def_rank,
        "location": _clean(row.get("location")),
    }


def _recent_games(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        _normalize_game(row)
        for row in (evidence.get("completed_games") or [])
        if isinstance(row, Mapping)
    ]
    return rows[-5:]


def _record_from_games(games: list[Mapping[str, Any]]) -> str:
    wins = sum(1 for row in games if row.get("result") == "W")
    losses = sum(1 for row in games if row.get("result") == "L")
    ties = sum(1 for row in games if row.get("result") == "T")
    if not games:
        return ""
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _avg(values: list[float]) -> float | None:
    return float(fmean(values)) if values else None


def _direct_metric(evidence: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _float(evidence.get(key))
        if value is not None:
            return value
    return None


def _trend(games: list[Mapping[str, Any]]) -> tuple[str, float | None]:
    margins = [
        float(row["points_for"]) - float(row["points_against"])
        for row in games
        if row.get("points_for") is not None and row.get("points_against") is not None
    ]
    # One or two completed games are real evidence, just not a stable trend.
    # Say that directly instead of making a valid early-season sample look broken.
    if len(margins) < 3:
        return "Early-season sample", None
    split = max(1, len(margins) // 2)
    older = margins[:split]
    newer = margins[split:]
    if not newer:
        return "Steady", 0.0
    delta = float(fmean(newer) - fmean(older))
    if delta >= 7.0:
        return "Improving", delta
    if delta <= -7.0:
        return "Slipping", delta
    return "Steady", delta


def _record_vs_winning(games: list[Mapping[str, Any]]) -> tuple[str, int]:
    known = [
        row for row in games
        if row.get("opponent_win_pct") is not None
    ]
    if not known:
        return "", 0
    qualifying = [
        row for row in known
        if float(row["opponent_win_pct"]) > 0.5
    ]
    wins = sum(1 for row in qualifying if row.get("result") == "W")
    losses = sum(1 for row in qualifying if row.get("result") == "L")
    ties = sum(1 for row in qualifying if row.get("result") == "T")
    return f"{wins}-{losses}" + (f"-{ties}" if ties else ""), len(qualifying)


def _opponent_quality_label(avg_pct: float | None) -> str:
    if avg_pct is None:
        return "Opponent quality incomplete"
    if avg_pct >= 0.60:
        return "Strong opponent slate"
    if avg_pct >= 0.50:
        return "Above-average opponent slate"
    if avg_pct <= 0.40:
        return "Soft opponent slate"
    return "Average opponent slate"


def _stat_rank(item: Mapping[str, Any]) -> int | None:
    headers = [_clean(x).lower() for x in item.get("headers") or []]
    row = list(item.get("row") or [])
    for idx, header in enumerate(headers):
        if header in {"rank", "rk"} or "rank" in header:
            if idx < len(row):
                rank = _int(row[idx])
                if rank is not None and rank > 0:
                    return rank
    if row:
        rank = _int(row[0])
        if rank is not None and rank > 0:
            return rank
    return None


@st.cache_data(ttl=300, show_spinner=False)
def _opponent_defense_rank_map(
    opponent_names: tuple[str, ...],
) -> tuple[dict[str, int], dict[str, Any]]:
    """Resolve current NCAA scoring-defense ranks for recent opponents.

    FBS is checked first, then unresolved names are checked against the FCS
    universe. Missing teams stay missing; no synthetic rank is created.
    """
    names = tuple(dict.fromkeys(_clean(name) for name in opponent_names if _usable(name)))
    if not names:
        return {}, {"requested": 0, "resolved": 0, "attempts": []}

    targets = {
        f"opp_{idx}": ncaa_team_data._team_keys(name, "")
        for idx, name in enumerate(names)
    }
    target_name = {f"opp_{idx}": name for idx, name in enumerate(names)}
    attempts: list[dict[str, Any]] = []
    ranks: dict[str, int] = {}

    index_html, index_attempts = ncaa_team_data._fetch_text_with_fallback(
        ncaa_team_data.NCAA_STATS_INDEX,
        "NCAA FBS scoring-defense index for Step 3 opponent quality",
    )
    attempts.extend(index_attempts)
    categories = (
        ncaa_team_data._discover_stat_categories(index_html)
        if index_html
        else {}
    )
    scoring_cfg = categories.get("scoring_defense")
    found: dict[str, dict[str, Any]] = {}
    if scoring_cfg:
        _, found, metric_attempts = ncaa_team_data._fetch_stat_metric(
            "scoring_defense",
            scoring_cfg,
            targets,
        )
        attempts.extend(metric_attempts)

    unresolved = dict(targets)
    for target, item in found.items():
        rank = _stat_rank(item)
        if rank is None:
            continue
        name = target_name[target]
        ranks[ncaa_team_data._canonical_name(name)] = rank
        unresolved.pop(target, None)

    if unresolved:
        fcs_html, fcs_index_attempts = ncaa_team_data._fetch_text_with_fallback(
            ncaa_team_data_v2.NCAA_FCS_STATS_INDEX,
            "NCAA FCS scoring-defense index for Step 3 opponent quality",
        )
        attempts.extend(fcs_index_attempts)
        fcs_categories = (
            ncaa_team_data_v2._fcs_categories(fcs_html)
            if fcs_html
            else {}
        )
        fcs_cfg = fcs_categories.get("scoring_defense")
        if fcs_cfg:
            _, fcs_found, fcs_attempts = ncaa_team_data._fetch_stat_metric(
                "scoring_defense",
                fcs_cfg,
                unresolved,
            )
            attempts.extend(fcs_attempts)
            for target, item in fcs_found.items():
                rank = _stat_rank(item)
                if rank is None:
                    continue
                name = target_name[target]
                ranks[ncaa_team_data._canonical_name(name)] = rank

    return ranks, {
        "requested": len(names),
        "resolved": len(ranks),
        "attempts": attempts,
    }


def _rank_sos_universe(
    ledgers: Mapping[str, Any],
) -> dict[str, int]:
    rows: list[tuple[str, float]] = []
    for key in ledgers:
        foundation = ncaa_team_data._schedule_foundation(key, ledgers)
        pct = _float(foundation.get("sos_opponent_win_pct"))
        coverage = _float(foundation.get("sos_coverage"))
        if pct is None or coverage is None or coverage <= 0:
            continue
        rows.append((str(key), float(pct)))
    rows.sort(key=lambda item: (-item[1], item[0]))
    return {key: idx + 1 for idx, (key, _) in enumerate(rows)}


@st.cache_data(ttl=300, show_spinner=False)
def _strength_of_schedule_rank_map(
    target_day: str,
) -> tuple[dict[str, int], dict[str, Any]]:
    """Rank current pre-target SOS from official NCAA schedule universes."""
    day = ncaa_schedule._day(target_day)
    season = ncaa_schedule._season_year(day)
    attempts: list[dict[str, Any]] = []
    ranks: dict[str, int] = {}

    fbs_payload, fbs_attempts = ncaa_schedule._fetch_json_with_fallback(
        ncaa_schedule.NCAA_SCHEDULE_URL,
        ncaa_schedule._ncaa_params(season),
        "NCAA FBS schedule for Step 3 SOS rank",
    )
    attempts.extend(fbs_attempts)
    if fbs_payload:
        fbs_ledgers, _, _ = ncaa_team_data._season_games_from_payload(
            fbs_payload,
            day,
        )
        ranks.update(_rank_sos_universe(fbs_ledgers))

    try:
        fcs_payload, fcs_attempts = ncaa_schedule_v2._fetch_ncaa_division_payload(
            season,
            ncaa_schedule_v2.NCAA_FCS_DIVISION,
        )
    except Exception as exc:
        fcs_payload, fcs_attempts = {}, [{
            "provider": "NCAA FCS schedule for Step 3 SOS rank",
            "error": f"{type(exc).__name__}: {exc}"[:260],
        }]
    attempts.extend(fcs_attempts)
    if fcs_payload:
        fcs_ledgers, _, _ = ncaa_team_data._season_games_from_payload(
            fcs_payload,
            day,
        )
        for key, rank in _rank_sos_universe(fcs_ledgers).items():
            ranks.setdefault(key, rank)

    return ranks, {
        "season": season,
        "ranked_teams": len(ranks),
        "attempts": attempts,
    }


def _lookup_sos_rank(team: Any, rank_map: Mapping[str, int]) -> int | None:
    key = ncaa_team_data._canonical_name(team)
    if key in rank_map:
        return int(rank_map[key])
    candidates = ncaa_team_data._team_keys(team, "")
    for row_key, rank in rank_map.items():
        if row_key in candidates or any(
            len(row_key) >= 5
            and len(candidate) >= 5
            and (row_key in candidate or candidate in row_key)
            for candidate in candidates
        ):
            return int(rank)
    return None


def _apply_opponent_quality(
    evidence: Mapping[str, Any],
    defense_ranks: Mapping[str, int],
    sos_rank: int | None,
) -> dict[str, Any]:
    out = dict(evidence or {})
    completed = [
        dict(row)
        for row in out.get("completed_games") or []
        if isinstance(row, Mapping)
    ]
    if not completed:
        if sos_rank is not None:
            out["strength_of_schedule_rank"] = int(sos_rank)
        return out

    for row in completed:
        opponent = _clean(row.get("opponent"))
        key = ncaa_team_data._canonical_name(opponent)
        rank = defense_ranks.get(key)
        if rank is not None:
            row["opponent_def_rank"] = int(rank)

    recent = completed[-5:]
    pcts = [
        float(row["opponent_record_pct"])
        for row in recent
        if row.get("opponent_record_pct") is not None
    ]
    ranks = [
        int(row["opponent_def_rank"])
        for row in recent
        if row.get("opponent_def_rank") is not None
        and int(row["opponent_def_rank"]) > 0
    ]
    out["completed_games"] = completed
    out["sos_opponent_win_pct"] = _avg(pcts)
    out["sos_coverage"] = len(pcts) / len(recent) if recent else 0.0
    out["avg_opponent_def_rank"] = (
        _avg([float(rank) for rank in ranks])
        if ranks
        else None
    )
    out["top40_defenses_faced"] = (
        sum(1 for rank in ranks if rank <= 40)
        if ranks
        else None
    )

    known = [
        row for row in recent
        if row.get("opponent_record_pct") is not None
    ]
    winning = [
        row for row in known
        if float(row["opponent_record_pct"]) > 0.5
    ]
    if known:
        wins = sum(1 for row in winning if _clean(row.get("result")).upper() == "W")
        losses = sum(1 for row in winning if _clean(row.get("result")).upper() == "L")
        ties = sum(1 for row in winning if _clean(row.get("result")).upper() == "T")
        out["record_vs_winning_teams"] = (
            f"{wins}-{losses}" + (f"-{ties}" if ties else "")
        )
        out["winning_opponents_faced"] = len(winning)

    if sos_rank is not None:
        out["strength_of_schedule_rank"] = int(sos_rank)
    return out


def _exact_team_id(
    identity_side: Mapping[str, Any],
    evidence: Mapping[str, Any],
    game: Mapping[str, Any],
    side: str,
) -> str:
    value = _clean(
        identity_side.get("team_id")
        or identity_side.get("espn_team_id")
        or evidence.get("espn_team_id")
        or game.get(f"{side}_espn_team_id")
    )
    return value if value.isdigit() else ""


def _overlay_exact_rows(
    evidence: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    out = dict(evidence or {})
    if not rows:
        return out

    completed: list[dict[str, Any]] = []
    for row in rows:
        pf = _float(row.get("points_for"))
        pa = _float(row.get("points_against"))
        if pf is None or pa is None:
            continue
        result = "W" if pf > pa else "L" if pf < pa else "T"
        completed.append({
            "event_id": _clean(row.get("event_id")),
            "date": _clean(row.get("date"))[:10],
            "opponent": _clean(row.get("opponent_name") or row.get("opponent")),
            "opponent_id": _clean(row.get("opponent_id")),
            "location": _clean(row.get("location")),
            "result": result,
            "points_for": pf,
            "points_against": pa,
            "score": f"{int(pf)}-{int(pa)}",
            "opponent_record_pct": row.get("opponent_record_pct"),
        })

    if not completed:
        return out

    recent = completed[-5:]
    out["completed_games"] = completed
    out["recent_record"] = {
        "wins": sum(1 for row in recent if row["result"] == "W"),
        "losses": sum(1 for row in recent if row["result"] == "L"),
        "ties": sum(1 for row in recent if row["result"] == "T"),
        "games": len(recent),
    }
    out["recent_form"] = "".join(row["result"] for row in recent)
    out["recent_ppg"] = _avg([float(row["points_for"]) for row in recent])
    out["recent_points_allowed_pg"] = _avg([float(row["points_against"]) for row in recent])
    out["recent_point_diff_pg"] = _avg([
        float(row["points_for"]) - float(row["points_against"])
        for row in recent
    ])
    opp_pcts = [
        float(row["opponent_record_pct"])
        for row in completed
        if row.get("opponent_record_pct") is not None
    ]
    if opp_pcts:
        out["sos_opponent_win_pct"] = _avg(opp_pcts)
        out["sos_coverage"] = len(opp_pcts) / len(completed)
    return out


def _snapshot_rows_for_team(
    team_id: str,
    target_day: str,
) -> list[dict[str, Any]]:
    """Return deterministic pre-target completed rows from the checked-in runtime snapshot."""
    if not _clean(team_id).isdigit():
        return []
    try:
        payload = json.loads(STEP3_RUNTIME_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    cutoff = _clean(target_day)[:10]
    rows: dict[str, dict[str, Any]] = {}
    for game in payload.get("games") or []:
        if not isinstance(game, Mapping):
            continue
        for side in ("away", "home"):
            profile = game.get(side)
            if not isinstance(profile, Mapping):
                continue
            if _clean(profile.get("team_id")) != _clean(team_id):
                continue
            for row in profile.get("completed_games") or []:
                if not isinstance(row, Mapping):
                    continue
                row_day = _clean(row.get("date"))[:10]
                if cutoff and row_day and row_day >= cutoff:
                    continue
                key = _clean(row.get("event_id")) or f"{row_day}|{_clean(row.get('opponent_id'))}"
                if key:
                    rows[key] = dict(row)

    return sorted(
        rows.values(),
        key=lambda row: _clean(row.get("date")),
    )


@st.cache_data(ttl=120, show_spinner=False)
def _candidate_game_days(
    team_name: str,
    team_slug: str,
    target_day: str,
    season: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Find this team's scheduled pre-target dates from the NCAA season slate."""
    keys = ncaa_team_data._team_keys(team_name, team_slug)
    if not keys or not _clean(target_day) or int(season or 0) < 1900:
        return [], []

    payload, attempts = ncaa_schedule._fetch_json_with_fallback(
        ncaa_schedule.NCAA_SCHEDULE_URL,
        ncaa_schedule._ncaa_params(int(season)),
        f"NCAA season schedule dates for Step 3 {team_name}",
    )
    if not payload:
        return [], list(attempts or [])

    target = _clean(target_day)[:10]
    days: set[str] = set()
    for contest in ncaa_schedule._walk_contests(payload):
        if not isinstance(contest, Mapping):
            continue
        pair = ncaa_team_data._contest_teams(contest)
        if pair is None:
            continue
        away_meta, home_meta = pair
        matched = False
        for meta in (away_meta, home_meta):
            meta_keys = ncaa_team_data._team_keys(
                meta.get("name"),
                meta.get("slug"),
            )
            if keys & meta_keys:
                matched = True
                break
        if not matched:
            continue

        dt = ncaa_schedule._contest_datetime(contest)
        if dt is None:
            continue
        day = dt.astimezone(ncaa_schedule._ET).date().isoformat()
        if day < target:
            days.add(day)

    # Five displayed games only need the five most recent scheduled dates.
    return sorted(days)[-5:], list(attempts or [])


@st.cache_data(ttl=120, show_spinner=False)
def _scoreboard_rows_for_team(
    team_id: str,
    game_days: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Recover exact completed results from ESPN's proven daily scoreboard."""
    rows: dict[str, dict[str, Any]] = {}
    attempts: list[dict[str, Any]] = []
    for day in game_days:
        try:
            payload, these_attempts = ncaa_schedule_v2._fetch_espn_fbs_payload(day)
        except Exception as exc:
            payload, these_attempts = {}, [{
                "provider": f"ESPN daily scoreboard Step 3 recovery {day}",
                "error": f"{type(exc).__name__}: {exc}"[:260],
            }]
        attempts.extend(list(these_attempts or []))
        for event in payload.get("events") or []:
            if not isinstance(event, Mapping):
                continue
            row = deep.history_engine._event_row(event, _clean(team_id))
            if not row:
                continue
            key = _clean(row.get("event_id")) or (
                f"{_clean(row.get('date'))}|{_clean(row.get('opponent_id'))}"
            )
            rows[key] = dict(row)

    ordered = sorted(
        rows.values(),
        key=lambda row: _clean(
            row.get("date")
            or getattr(row.get("date_dt"), "isoformat", lambda: "")()
        ),
    )
    return ordered[-5:], attempts


@st.cache_data(ttl=120, show_spinner=False)
@st.cache_data(ttl=120, show_spinner=False)
def _scoreboard_range_events(
    target_day: str,
    *,
    lookback_days: int = 70,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return deduped completed pre-target ESPN CFB events for FBS + FCS."""
    target_text = _clean(target_day)[:10]
    if not target_text:
        return [], []
    try:
        target = date.fromisoformat(target_text)
    except Exception:
        return [], []

    start_day = target - timedelta(days=max(14, int(lookback_days)))
    end_day = target - timedelta(days=1)
    if end_day < start_day:
        return [], []

    date_range = f"{start_day.strftime('%Y%m%d')}-{end_day.strftime('%Y%m%d')}"
    events: dict[str, dict[str, Any]] = {}
    attempts: list[dict[str, Any]] = []

    for group in ("80", "81"):
        payload, these_attempts = ncaa_schedule._fetch_json_with_fallback(
            ncaa_schedule.ESPN_SCOREBOARD_URL,
            {"dates": date_range, "limit": 1000, "groups": group},
            f"ESPN CFB scoreboard range group {group} for Step 3",
        )
        attempts.extend(list(these_attempts or []))
        for event in payload.get("events") or []:
            if not isinstance(event, Mapping):
                continue
            if not deep.history_engine._completed(event):
                continue
            event_id = _clean(event.get("id"))
            if not event_id:
                comp = deep.history_engine._competition(event)
                event_id = _clean(comp.get("id"))
            if not event_id:
                continue
            raw_date = _clean(
                event.get("date")
                or deep.history_engine._competition(event).get("date")
            )[:10]
            if raw_date and raw_date >= target_text:
                continue
            events[event_id] = dict(event)

    ordered = sorted(
        events.values(),
        key=lambda event: _clean(
            event.get("date")
            or deep.history_engine._competition(event).get("date")
        ),
    )
    return ordered, attempts


def _scoreboard_range_rows_for_team(
    team_id: str,
    target_day: str,
    *,
    lookback_days: int = 70,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Recover exact completed results from the shared pre-kickoff event universe."""
    team_id = _clean(team_id)
    if not team_id.isdigit():
        return [], []
    events, attempts = _scoreboard_range_events(
        target_day,
        lookback_days=lookback_days,
    )
    rows: dict[str, dict[str, Any]] = {}
    for event in events:
        row = deep.history_engine._event_row(event, team_id)
        if not row:
            continue
        key = _clean(row.get("event_id")) or (
            f"{_clean(row.get('date'))}|{_clean(row.get('opponent_id'))}"
        )
        if key:
            rows[key] = dict(row)
    ordered = sorted(
        rows.values(),
        key=lambda row: _clean(
            row.get("date")
            or getattr(row.get("date_dt"), "isoformat", lambda: "")()
        ),
    )
    return ordered[-5:], attempts


@st.cache_data(ttl=120, show_spinner=False)
def _scoreboard_quality_universe(
    target_day: str,
    *,
    lookback_days: int = 70,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build pregame opponent records, scoring-defense ranks, and SOS ranks."""
    events, attempts = _scoreboard_range_events(
        target_day,
        lookback_days=lookback_days,
    )
    games: dict[str, list[dict[str, Any]]] = {}

    for event in events:
        comp = deep.history_engine._competition(event)
        competitors = [
            row for row in (comp.get("competitors") or [])
            if isinstance(row, Mapping)
        ]
        if len(competitors) < 2:
            continue

        parsed: list[dict[str, Any]] = []
        for competitor in competitors:
            team = competitor.get("team") or {}
            if not isinstance(team, Mapping):
                team = {}
            team_id = _clean(team.get("id"))
            score = deep.history_engine._float(competitor.get("score"))
            if not team_id.isdigit() or score is None:
                continue
            parsed.append({
                "team_id": team_id,
                "team_name": _clean(
                    team.get("displayName")
                    or team.get("shortDisplayName")
                    or team.get("location")
                ),
                "score": float(score),
            })
        if len(parsed) != 2:
            continue

        a, b = parsed
        for mine, opp in ((a, b), (b, a)):
            pf = float(mine["score"])
            pa = float(opp["score"])
            result = "W" if pf > pa else "L" if pf < pa else "T"
            games.setdefault(mine["team_id"], []).append({
                "opponent_id": opp["team_id"],
                "opponent": opp["team_name"],
                "points_for": pf,
                "points_against": pa,
                "result": result,
            })

    records: dict[str, float] = {}
    allowed_pg: dict[str, float] = {}
    for team_id, rows in games.items():
        if not rows:
            continue
        wins = sum(1 for row in rows if row["result"] == "W")
        ties = sum(1 for row in rows if row["result"] == "T")
        records[team_id] = (wins + 0.5 * ties) / len(rows)
        allowed_value = _avg([float(row["points_against"]) for row in rows])
        if allowed_value is not None:
            allowed_pg[team_id] = float(allowed_value)

    defense_order = sorted(
        allowed_pg.items(),
        key=lambda item: (item[1], item[0]),
    )
    defense_ranks = {
        team_id: idx + 1
        for idx, (team_id, _) in enumerate(defense_order)
    }

    sos_values: dict[str, float] = {}
    for team_id, rows in games.items():
        opponent_pcts = [
            records[row["opponent_id"]]
            for row in rows
            if row.get("opponent_id") in records
        ]
        value = _avg([float(v) for v in opponent_pcts])
        if value is not None:
            sos_values[team_id] = float(value)

    sos_order = sorted(
        sos_values.items(),
        key=lambda item: (-item[1], item[0]),
    )
    sos_ranks = {
        team_id: idx + 1
        for idx, (team_id, _) in enumerate(sos_order)
    }

    return {
        "records": records,
        "defense_allowed_pg": allowed_pg,
        "defense_ranks": defense_ranks,
        "sos_values": sos_values,
        "sos_ranks": sos_ranks,
        "team_count": len(games),
        "event_count": len(events),
    }, {
        "events": len(events),
        "teams": len(games),
        "record_teams": len(records),
        "defense_rank_teams": len(defense_ranks),
        "sos_rank_teams": len(sos_ranks),
        "attempts": attempts,
    }


def _apply_scoreboard_quality(
    evidence: Mapping[str, Any],
    team_id: str,
    universe: Mapping[str, Any],
) -> dict[str, Any]:
    out = dict(evidence or {})
    completed = [
        dict(row)
        for row in out.get("completed_games") or []
        if isinstance(row, Mapping)
    ]
    recent = completed[-5:]
    records = universe.get("records") or {}
    defense_ranks = universe.get("defense_ranks") or {}

    for row in recent:
        opponent_id = _clean(row.get("opponent_id"))
        if opponent_id in records:
            row["opponent_record_pct"] = float(records[opponent_id])
        if opponent_id in defense_ranks:
            row["opponent_def_rank"] = int(defense_ranks[opponent_id])

    if recent:
        completed = completed[:-len(recent)] + recent
    out["completed_games"] = completed

    pcts = [
        float(row["opponent_record_pct"])
        for row in recent
        if row.get("opponent_record_pct") is not None
    ]
    ranks = [
        int(row["opponent_def_rank"])
        for row in recent
        if row.get("opponent_def_rank") is not None
    ]
    out["sos_opponent_win_pct"] = _avg(pcts)
    out["sos_coverage"] = len(pcts) / len(recent) if recent else 0.0
    out["avg_opponent_def_rank"] = (
        _avg([float(rank) for rank in ranks]) if ranks else None
    )
    out["top40_defenses_faced"] = (
        sum(1 for rank in ranks if rank <= 40) if ranks else None
    )

    known = [
        row for row in recent
        if row.get("opponent_record_pct") is not None
    ]
    winning = [
        row for row in known
        if float(row["opponent_record_pct"]) > 0.5
    ]
    if known:
        wins = sum(
            1 for row in winning
            if _clean(row.get("result")).upper() == "W"
        )
        losses = sum(
            1 for row in winning
            if _clean(row.get("result")).upper() == "L"
        )
        ties = sum(
            1 for row in winning
            if _clean(row.get("result")).upper() == "T"
        )
        out["record_vs_winning_teams"] = (
            f"{wins}-{losses}" + (f"-{ties}" if ties else "")
        )
        out["winning_opponents_faced"] = len(winning)

    sos_ranks = universe.get("sos_ranks") or {}
    sos_values = universe.get("sos_values") or {}
    team_key = _clean(team_id)
    if team_key in sos_ranks:
        out["strength_of_schedule_rank"] = int(sos_ranks[team_key])
    if team_key in sos_values:
        out["sos_opponent_win_pct"] = float(sos_values[team_key])

    return out


def _merge_exact_game_rows(
    *groups: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for group in groups:
        for raw in group or []:
            if not isinstance(raw, Mapping):
                continue
            key = _clean(raw.get("event_id")) or (
                f"{_clean(raw.get('date'))}|{_clean(raw.get('opponent_id'))}"
            )
            if key:
                rows[key] = dict(raw)
    return sorted(
        rows.values(),
        key=lambda row: _clean(
            row.get("date")
            or getattr(row.get("date_dt"), "isoformat", lambda: "")()
        ),
    )[-5:]


def enrich_step3_inputs(
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
    game: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Refresh Step 3 core form and hydrate opponent quality fail-closed."""
    identity = identity or {}
    game = game or {}
    outputs: dict[str, dict[str, Any]] = {
        "away": dict(away or {}),
        "home": dict(home or {}),
    }
    diag: dict[str, Any] = {"away": {}, "home": {}}

    try:
        season = int(deep._season(game))
        cutoff = deep._cutoff(game)
    except Exception:
        season = 0
        cutoff = None
    event_id = _clean(game.get("espn_event_id"))
    target_day = _clean(game.get("game_date"))[:10]

    # Phase 1 — exact completed-game truth for each selected team.
    for side in ("away", "home"):
        current = outputs[side]
        identity_side = (
            identity.get(side) or {}
            if isinstance(identity, Mapping)
            else {}
        )
        team_id = _exact_team_id(identity_side, current, game, side)

        if not team_id:
            diag[side] = {
                "refresh_used": False,
                "fallback_used": False,
                "reason": "exact_team_id_unavailable",
                "team_id": "",
            }
            continue

        attempts: list[dict[str, Any]] = []
        live_rows: list[Mapping[str, Any]] = []
        if season and cutoff is not None:
            try:
                payload, attempts = deep.history_engine._fetch_team_schedule(
                    team_id,
                    int(season),
                )
                live_rows = deep.form_engine._current_season_rows(
                    payload,
                    team_id,
                    int(season),
                    cutoff,
                    event_id,
                )
                live_rows = sorted(
                    live_rows,
                    key=lambda row: _clean(
                        row.get("date")
                        or getattr(row.get("date_dt"), "isoformat", lambda: "")()
                    ),
                )
            except Exception as exc:
                live_rows = []
                attempts = [{
                    "provider": (
                        f"ESPN exact team {team_id} current-season Step 3 truth refresh"
                    ),
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                }]

        # The team-schedule endpoint is not reliable enough by itself in the
        # live app. Recover the same exact team from ESPN's daily scoreboard
        # on NCAA-scheduled pre-kickoff dates, then merge/dedupe the two feeds.
        team_name = _clean(
            current.get("team")
            or identity_side.get("team")
            or identity_side.get("team_name")
        )
        team_slug = _clean(
            current.get("team_slug")
            or identity_side.get("team_slug")
        )
        candidate_days: list[str] = []
        date_attempts: list[dict[str, Any]] = []
        scoreboard_rows: list[Mapping[str, Any]] = []
        scoreboard_attempts: list[dict[str, Any]] = []
        if season and target_day:
            try:
                candidate_days, date_attempts = _candidate_game_days(
                    team_name,
                    team_slug,
                    target_day,
                    int(season),
                )
                if candidate_days:
                    scoreboard_rows, scoreboard_attempts = _scoreboard_rows_for_team(
                        team_id,
                        tuple(candidate_days),
                    )
            except Exception as exc:
                scoreboard_attempts = [{
                    "provider": f"Step 3 scoreboard recovery for exact team {team_id}",
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                }]

        range_rows: list[Mapping[str, Any]] = []
        range_attempts: list[dict[str, Any]] = []
        if target_day:
            try:
                range_rows, range_attempts = _scoreboard_range_rows_for_team(
                    team_id,
                    target_day,
                )
            except Exception as exc:
                range_attempts = [{
                    "provider": f"Step 3 scoreboard range recovery for exact team {team_id}",
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                }]

        exact_rows = _merge_exact_game_rows(
            list(live_rows),
            list(scoreboard_rows),
            list(range_rows),
        )
        combined_attempts = (
            list(attempts or [])
            + list(date_attempts or [])
            + list(scoreboard_attempts or [])
            + list(range_attempts or [])
        )
        if exact_rows:
            outputs[side] = _overlay_exact_rows(current, exact_rows)
            diag[side] = {
                "refresh_used": True,
                "fallback_used": False,
                "source": (
                    "scoreboard_range_recovery"
                    if range_rows and not live_rows and not scoreboard_rows
                    else "live_exact_schedule+scoreboard_range"
                    if range_rows and live_rows and not scoreboard_rows
                    else "daily_scoreboard+scoreboard_range"
                    if range_rows and scoreboard_rows and not live_rows
                    else "live_exact_schedule+daily_scoreboard+scoreboard_range"
                    if range_rows and scoreboard_rows and live_rows
                    else "live_exact_schedule+daily_scoreboard"
                    if live_rows and scoreboard_rows
                    else "daily_scoreboard_recovery"
                    if scoreboard_rows
                    else "live_exact_schedule"
                ),
                "team_id": team_id,
                "rows": len(exact_rows),
                "team_schedule_rows": len(live_rows),
                "scoreboard_rows": len(scoreboard_rows),
                "scoreboard_range_rows": len(range_rows),
                "candidate_days": list(candidate_days),
                "attempts": combined_attempts,
            }
            continue

        current_contract = build_team_form_contract(
            current,
            identity_side,
            side=side,
        )
        if current_contract.get("required_complete"):
            diag[side] = {
                "refresh_used": False,
                "fallback_used": False,
                "source": "existing_verified_evidence",
                "reason": "live_schedule_unavailable_current_core_preserved",
                "team_id": team_id,
                "rows": int(current_contract.get("sample_games") or 0),
                "attempts": attempts,
            }
            continue

        snapshot_rows = _snapshot_rows_for_team(team_id, target_day)
        snapshot_overlay = _overlay_exact_rows(current, snapshot_rows)
        snapshot_contract = build_team_form_contract(
            snapshot_overlay,
            identity_side,
            side=side,
        )
        outputs[side] = snapshot_overlay
        diag[side] = {
            "refresh_used": False,
            "fallback_used": bool(snapshot_rows),
            "source": "checked_in_runtime_snapshot",
            "team_id": team_id,
            "rows": len(snapshot_rows),
            "required_complete": bool(snapshot_contract.get("required_complete")),
            "attempts": attempts,
        }

    # Phase 1B — derive opponent quality from the same exact pregame
    # scoreboard universe before any per-opponent fallback is attempted.
    quality_universe: dict[str, Any] = {}
    quality_universe_diag: dict[str, Any] = {"attempts": []}
    if target_day:
        try:
            quality_universe, quality_universe_diag = _scoreboard_quality_universe(
                target_day
            )
        except Exception as exc:
            quality_universe_diag = {
                "attempts": [{
                    "provider": "ESPN scoreboard Step 3 quality universe",
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                }]
            }

    for side in ("away", "home"):
        team_id = _clean((diag.get(side) or {}).get("team_id"))
        if team_id and quality_universe:
            outputs[side] = _apply_scoreboard_quality(
                outputs[side],
                team_id,
                quality_universe,
            )
        diag[side]["scoreboard_quality_universe"] = {
            key: value
            for key, value in quality_universe_diag.items()
            if key != "attempts"
        }
        diag[side].setdefault("attempts", [])
        diag[side]["attempts"] = (
            list(diag[side].get("attempts") or [])
            + list(quality_universe_diag.get("attempts") or [])
        )

    # Phase 2 — exact opponent records for only the displayed recent window.
    opponent_names: list[str] = []
    for side in ("away", "home"):
        current = dict(outputs[side])
        completed = [
            dict(row)
            for row in current.get("completed_games") or []
            if isinstance(row, Mapping)
        ]
        recent = completed[-5:]
        quality_attempts: list[dict[str, Any]] = []
        record_diag: dict[str, Any] = {
            "inline_records": 0,
            "fallback_requested": 0,
            "fallback_resolved": 0,
            "attempts": [],
        }
        if recent and season and cutoff is not None:
            try:
                hydrated, record_diag = deep.form_engine._hydrate_opponent_records(
                    recent,
                    int(season),
                    cutoff,
                    event_id,
                )
                quality_attempts.extend(record_diag.get("attempts") or [])
                completed = completed[:-len(recent)] + hydrated
                current["completed_games"] = completed
            except Exception as exc:
                quality_attempts.append({
                    "provider": "ESPN exact opponent records for Step 3",
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                })

        outputs[side] = current
        for row in (current.get("completed_games") or [])[-5:]:
            if isinstance(row, Mapping) and _usable(row.get("opponent")):
                opponent_names.append(_clean(row.get("opponent")))
        diag[side]["opponent_record_resolution"] = {
            key: value
            for key, value in record_diag.items()
            if key != "attempts"
        }
        diag[side].setdefault("attempts", [])
        diag[side]["attempts"] = (
            list(diag[side].get("attempts") or []) + quality_attempts
        )

    # Phase 3 — official NCAA scoring-defense ranks and pre-target SOS rank.
    defense_ranks: dict[str, int] = {}
    defense_diag: dict[str, Any] = {"requested": 0, "resolved": 0, "attempts": []}
    if opponent_names:
        try:
            defense_ranks, defense_diag = _opponent_defense_rank_map(
                tuple(opponent_names)
            )
        except Exception as exc:
            defense_diag = {
                "requested": len(opponent_names),
                "resolved": 0,
                "attempts": [{
                    "provider": "NCAA opponent scoring-defense ranks for Step 3",
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                }],
            }

    sos_ranks: dict[str, int] = {}
    sos_diag: dict[str, Any] = {"ranked_teams": 0, "attempts": []}
    if target_day:
        try:
            sos_ranks, sos_diag = _strength_of_schedule_rank_map(target_day)
        except Exception as exc:
            sos_diag = {
                "ranked_teams": 0,
                "attempts": [{
                    "provider": "NCAA schedule-strength rank for Step 3",
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                }],
            }

    for side in ("away", "home"):
        team_name = (
            outputs[side].get("team")
            or (identity.get(side) or {}).get("team")
            or (identity.get(side) or {}).get("team_name")
        )
        sos_rank = _lookup_sos_rank(team_name, sos_ranks)
        outputs[side] = _apply_opponent_quality(
            outputs[side],
            defense_ranks,
            sos_rank,
        )
        diag[side]["opponent_defense_rank_resolution"] = {
            "requested": int(defense_diag.get("requested") or 0),
            "resolved": int(defense_diag.get("resolved") or 0),
        }
        diag[side]["strength_of_schedule_rank"] = sos_rank
        diag[side].setdefault("attempts", [])
        diag[side]["attempts"] = (
            list(diag[side].get("attempts") or [])
            + list(defense_diag.get("attempts") or [])
            + list(sos_diag.get("attempts") or [])
        )

    return outputs["away"], outputs["home"], diag

def build_team_form_contract(
    evidence: Mapping[str, Any] | None,
    identity_side: Mapping[str, Any] | None = None,
    *,
    side: str = "",
) -> dict[str, Any]:
    evidence = evidence or {}
    identity_side = identity_side or {}
    games = _recent_games(evidence)

    team = _clean(evidence.get("team") or identity_side.get("team") or identity_side.get("team_name"))
    logo = _clean(identity_side.get("logo") or evidence.get("logo"))
    conference = _clean(evidence.get("conference") or identity_side.get("conference"))

    last5_record = _clean(evidence.get("recent_record_text"))
    if not _usable(last5_record):
        recent_record = evidence.get("recent_record")
        if isinstance(recent_record, Mapping):
            wins = int(recent_record.get("wins") or 0)
            losses = int(recent_record.get("losses") or 0)
            ties = int(recent_record.get("ties") or 0)
            total = int(recent_record.get("games") or wins + losses + ties)
            if total:
                last5_record = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    if not _usable(last5_record):
        last5_record = _record_from_games(games)

    scored = [float(row["points_for"]) for row in games if row.get("points_for") is not None]
    allowed = [float(row["points_against"]) for row in games if row.get("points_against") is not None]
    recent_ppg = _direct_metric(evidence, "recent_ppg")
    if recent_ppg is None:
        recent_ppg = _avg(scored)
    recent_allowed = _direct_metric(evidence, "recent_points_allowed_pg", "recent_allowed_pg")
    if recent_allowed is None:
        recent_allowed = _avg(allowed)
    recent_diff = _direct_metric(evidence, "recent_point_diff_pg")
    if recent_diff is None and recent_ppg is not None and recent_allowed is not None:
        recent_diff = recent_ppg - recent_allowed

    row_pcts = [
        float(row["opponent_win_pct"])
        for row in games
        if row.get("opponent_win_pct") is not None
    ]
    avg_opp_pct = _direct_metric(evidence, "sos_opponent_win_pct", "avg_opponent_win_pct")
    if avg_opp_pct is None:
        avg_opp_pct = _avg(row_pcts)
    if avg_opp_pct is not None and avg_opp_pct > 1:
        avg_opp_pct /= 100.0

    sos_coverage = _direct_metric(evidence, "sos_coverage")
    if sos_coverage is None and games:
        sos_coverage = len(row_pcts) / len(games)
    if sos_coverage is not None and sos_coverage > 1:
        sos_coverage /= 100.0

    opp_def_ranks = [
        int(row["opponent_def_rank"])
        for row in games
        if row.get("opponent_def_rank") is not None and int(row["opponent_def_rank"]) > 0
    ]
    avg_opp_def_rank = _direct_metric(evidence, "avg_opponent_def_rank")
    if avg_opp_def_rank is None and opp_def_ranks:
        avg_opp_def_rank = _avg([float(x) for x in opp_def_ranks])

    top40 = _int(evidence.get("top40_defenses_faced"))
    if top40 is None and opp_def_ranks:
        top40 = sum(1 for rank in opp_def_ranks if rank <= 40)

    record_vs_winning = _clean(evidence.get("record_vs_winning_teams"))
    winning_faced = _int(evidence.get("winning_opponents_faced"))
    if not _usable(record_vs_winning):
        record_vs_winning, derived_count = _record_vs_winning(games)
        if winning_faced is None:
            winning_faced = derived_count

    sos_rank = _int(
        evidence.get("strength_of_schedule_rank")
        or evidence.get("sos_rank")
        or evidence.get("schedule_strength_rank")
    )

    trend_direction, trend_delta = _trend(games)
    trend_detail = (
        f"{len(games)} completed game" + ("" if len(games) == 1 else "s")
        if len(games) < 3
        else (_record_from_games(games) or "Current sample")
    )

    contract: dict[str, Any] = {
        "side": side,
        "team": team,
        "logo": logo,
        "conference": conference,
        "sample_games": len(games),
        "games": games,
        "last5_record": last5_record,
        "recent_ppg": recent_ppg,
        "recent_allowed_pg": recent_allowed,
        "recent_diff_pg": recent_diff,
        "avg_opponent_win_pct": avg_opp_pct,
        "sos_coverage": sos_coverage,
        "avg_opponent_def_rank": avg_opp_def_rank,
        "top40_defenses_faced": top40,
        "record_vs_winning_teams": record_vs_winning,
        "winning_opponents_faced": winning_faced,
        "strength_of_schedule_rank": sos_rank,
        "trend_direction": trend_direction,
        "trend_delta": trend_delta,
        "trend_detail": trend_detail,
        "opponent_quality_label": _opponent_quality_label(avg_opp_pct),
    }

    missing_required: list[str] = []
    for field in STEP3_REQUIRED_FIELDS:
        value = contract.get(field)
        if field == "sample_games":
            if int(value or 0) <= 0:
                missing_required.append(field)
        elif field in {"recent_ppg", "recent_allowed_pg", "recent_diff_pg"}:
            if value is None:
                missing_required.append(field)
        elif not _usable(value):
            missing_required.append(field)

    missing_advanced = [
        field for field in STEP3_ADVANCED_FIELDS
        if contract.get(field) is None
        or (field == "record_vs_winning_teams" and not _usable(contract.get(field)))
    ]

    record_coverage = float(sos_coverage or 0.0)
    defense_rank_coverage = (
        len(opp_def_ranks) / len(games)
        if games
        else 0.0
    )
    opponent_quality_coverage = min(record_coverage, defense_rank_coverage)
    opponent_quality_ready = bool(
        not missing_advanced
        and record_coverage >= STEP3_MIN_OPPONENT_QUALITY_COVERAGE
        and defense_rank_coverage >= STEP3_MIN_OPPONENT_QUALITY_COVERAGE
    )

    if missing_required:
        state = "DATA LIMITED"
        status_reason = (
            "Core recent-form evidence is incomplete: "
            + ", ".join(str(field).replace("_", " ") for field in missing_required)
        )
    elif not opponent_quality_ready:
        state = "CHECK"
        if missing_advanced:
            status_reason = (
                "Opponent quality is still checking: "
                + ", ".join(str(field).replace("_", " ") for field in missing_advanced)
            )
        else:
            status_reason = (
                "Opponent quality coverage is below the 60% READY threshold "
                f"(records {record_coverage:.0%}, defense ranks {defense_rank_coverage:.0%})."
            )
    else:
        state = "READY"
        status_reason = (
            "Recent form and opponent quality meet the Step 3 READY contract "
            f"(records {record_coverage:.0%}, defense ranks {defense_rank_coverage:.0%})."
        )

    wins = sum(1 for row in games if row.get("result") == "W")
    win_rate = wins / len(games) if games else 0.0
    form_score = float(recent_diff or 0.0) + win_rate * 10.0
    if avg_opp_pct is not None:
        form_score += (avg_opp_pct - 0.5) * 16.0

    contract["missing_required"] = missing_required
    contract["missing_advanced"] = missing_advanced
    contract["required_complete"] = not missing_required
    contract["opponent_record_coverage"] = record_coverage
    contract["opponent_defense_rank_coverage"] = defense_rank_coverage
    contract["opponent_quality_coverage"] = opponent_quality_coverage
    contract["opponent_quality_ready"] = opponent_quality_ready
    contract["status_reason"] = status_reason
    contract["state"] = state
    contract["form_score"] = form_score
    return contract


def _fmt_num(value: Any, signed: bool = False) -> str:
    number = _float(value)
    if number is None:
        return "—"
    return f"{number:+.1f}" if signed else f"{number:.1f}"


def _fmt_pct(value: Any) -> str:
    number = _float(value)
    if number is None:
        return "—"
    if number <= 1.0:
        number *= 100.0
    return f"{number:.0f}%"


def _takeaways(away: Mapping[str, Any], home: Mapping[str, Any]) -> list[str]:
    rows: list[str] = []
    for team in (away, home):
        name = _clean(team.get("team")) or "Team"
        trend = _clean(team.get("trend_direction"))
        if trend in {"Improving", "Slipping"}:
            rows.append(f"{name} is {trend.lower()} across the current completed-game sample.")
    if away.get("recent_ppg") is not None and home.get("recent_ppg") is not None:
        leader = away if float(away["recent_ppg"]) >= float(home["recent_ppg"]) else home
        rows.append(f"{_clean(leader.get('team'))} owns the stronger recent scoring average.")
    if away.get("recent_allowed_pg") is not None and home.get("recent_allowed_pg") is not None:
        leader = away if float(away["recent_allowed_pg"]) <= float(home["recent_allowed_pg"]) else home
        rows.append(f"{_clean(leader.get('team'))} has allowed fewer points recently.")
    if away.get("avg_opponent_win_pct") is not None and home.get("avg_opponent_win_pct") is not None:
        leader = away if float(away["avg_opponent_win_pct"]) >= float(home["avg_opponent_win_pct"]) else home
        rows.append(f"{_clean(leader.get('team'))} has faced the stronger opponent win-rate profile.")
    if not rows:
        rows.append("Opponent-adjusted form evidence is incomplete, so Step 3 does not force a strong conclusion.")
    return rows[:5]


def build_step3_contract(
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
) -> dict[str, Any]:
    identity = identity or {}
    a = build_team_form_contract(away, identity.get("away") or {}, side="away")
    h = build_team_form_contract(home, identity.get("home") or {}, side="home")
    states = {a["state"], h["state"]}
    state = "DATA LIMITED" if "DATA LIMITED" in states else "CHECK" if "CHECK" in states else "READY"

    delta = float(a.get("form_score") or 0.0) - float(h.get("form_score") or 0.0)
    if abs(delta) < 2.5:
        edge_team = "Even"
        edge_label = "No clear form edge"
    else:
        edge = a if delta > 0 else h
        edge_team = _clean(edge.get("team"))
        edge_label = ("Clear edge" if abs(delta) >= 10 else "Slight edge") + f": {edge_team}"

    reason = "Recent scoring, prevention, trend, and opponent quality are compared without changing the model projection."
    return {
        "away": a,
        "home": h,
        "state": state,
        "ready": state == "READY",
        "edge_team": edge_team,
        "edge_label": edge_label,
        "edge_reason": reason,
        "takeaways": _takeaways(a, h),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }


def _game_rows(team: Mapping[str, Any]) -> str:
    rows = []
    for row in team.get("games") or []:
        result = _clean(row.get("result"))
        css = "win" if result == "W" else "loss" if result == "L" else "tie"
        score = "—"
        if row.get("points_for") is not None and row.get("points_against") is not None:
            score = f"{int(float(row['points_for']))}-{int(float(row['points_against']))}"
        rows.append(
            "<tr>"
            f"<td>{escape(_clean(row.get('date'))[-5:])}</td>"
            f"<td>{escape(_clean(row.get('opponent')))}</td>"
            f'<td class="result {css}">{escape(result)} {escape(score)}</td>'
            f"<td>{escape(_fmt_num(row.get('points_for')))}</td>"
            f"<td>{escape(_fmt_num(row.get('points_against')))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="5">No verified completed-game rows.</td></tr>')
    return "".join(rows)


def _opp_rows(team: Mapping[str, Any]) -> str:
    rows = (
        ("Avg Opponent Win %", _fmt_pct(team.get("avg_opponent_win_pct"))),
        ("Avg Opponent Defense Rank", _fmt_num(team.get("avg_opponent_def_rank"))),
        ("Top 40 Defenses Faced", _clean(team.get("top40_defenses_faced")) or "—"),
        ("Record vs Winning Teams", _clean(team.get("record_vs_winning_teams")) or "—"),
        ("Strength of Schedule", f"#{int(team['strength_of_schedule_rank'])}" if team.get("strength_of_schedule_rank") is not None else "—"),
    )
    return "".join(
        f'<div class="gt168-opp-row"><span>{escape(label)}</span><b>{escape(value)}</b></div>'
        for label, value in rows
    )


def _team_card(team: Mapping[str, Any], *, home_side: bool) -> str:
    logo = _clean(team.get("logo"))
    logo_html = (
        f'<img class="gt168-logo" src="{escape(logo)}" alt="{escape(_clean(team.get("team")))} logo"/>'
        if logo else '<span style="font-size:24px">🏈</span>'
    )
    diff = team.get("recent_diff_pg")
    diff_css = "good" if diff is not None and float(diff) >= 0 else "bad"
    missing = list(team.get("missing_required") or []) + list(team.get("missing_advanced") or [])
    reason = _clean(team.get("status_reason"))
    raw_coverage = team.get("opponent_quality_coverage")
    coverage = float(raw_coverage) if raw_coverage is not None else None
    missing_html = ""
    if team.get("state") != "READY":
        coverage_text = (
            f" • Opponent-quality coverage {coverage:.0%}"
            if coverage is not None
            else ""
        )
        detail = reason or (
            "Still checking: "
            + ", ".join(str(x).replace("_", " ").title() for x in missing)
            if missing
            else "Step 3 evidence is still checking."
        )
        missing_html = (
            f'<div class="gt168-missing" data-testid="gt168-step3-status-reason">'
            f'{escape(_clean(team.get("state")))} — {escape(detail)}{escape(coverage_text)}</div>'
        )
    return f"""
<div class="gt168-team {'home' if home_side else 'away'}" data-testid="gt168-step3-{'home' if home_side else 'away'}">
  <div class="gt168-head">
    <div>{logo_html}</div>
    <div class="gt168-name"><b>{escape(_clean(team.get('team')) or ('Home' if home_side else 'Away'))}</b><span>{escape(_clean(team.get('conference')) or 'Current form')}</span></div>
    <div class="gt168-form-record"><b>{escape(_clean(team.get('last5_record')) or '—')}</b><span>Last 5</span></div>
  </div>
  <div class="gt168-table-wrap">
    <div class="gt168-table-title">Last 5 Games</div>
    <table class="gt168-table"><thead><tr><th>Date</th><th>Opponent</th><th>Result</th><th>Pts</th><th>Allowed</th></tr></thead><tbody>{_game_rows(team)}</tbody></table>
  </div>
  <div class="gt168-table-title" style="padding:0 8px 5px">Recent Averages</div>
  <div class="gt168-recent">
    <div class="gt168-metric"><b>{escape(_fmt_num(team.get('recent_ppg')))}</b><span>PPG</span></div>
    <div class="gt168-metric"><b>{escape(_fmt_num(team.get('recent_allowed_pg')))}</b><span>Allowed</span></div>
    <div class="gt168-metric {diff_css}"><b>{escape(_fmt_num(diff, signed=True))}</b><span>Diff</span></div>
  </div>
  <div class="gt168-opp">
    <div class="gt168-opp-title"><span>🎯 Opponent Quality</span><span>{escape(_clean(team.get('opponent_quality_label')))}</span></div>
    {_opp_rows(team)}
  </div>
  {missing_html}
</div>"""


def render_step3_html(
    status: str,
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
) -> str:
    contract = build_step3_contract(identity, away, home)
    a, h = contract["away"], contract["home"]
    state = _clean(contract["state"])
    state_css = "ready" if state == "READY" else "limited" if state == "DATA LIMITED" else "check"

    a_trend = _clean(a.get("trend_direction"))
    h_trend = _clean(h.get("trend_direction"))
    takeaway_html = "".join(f"<div>{escape(item)}</div>" for item in contract["takeaways"])
    subtitle = "Last 3–5 Games • Trend Direction • Strength of Opponents • Adjusted Performance"

    center = f"""
<div class="gt168-center">
  <div class="gt168-center-card" data-testid="gt168-step3-comparison">
    <div class="gt168-center-title">FORM COMPARISON</div>
    <div class="gt168-compare-row"><b>{escape(_clean(a.get('last5_record')) or '—')}</b><span>Last 5 Record</span><b>{escape(_clean(h.get('last5_record')) or '—')}</b></div>
    <div class="gt168-compare-row"><b>{escape(_fmt_num(a.get('recent_ppg')))}</b><span>Avg PPG</span><b>{escape(_fmt_num(h.get('recent_ppg')))}</b></div>
    <div class="gt168-compare-row"><b>{escape(_fmt_num(a.get('recent_allowed_pg')))}</b><span>Avg Allowed</span><b>{escape(_fmt_num(h.get('recent_allowed_pg')))}</b></div>
    <div class="gt168-compare-row"><b>{escape(_fmt_num(a.get('recent_diff_pg'), signed=True))}</b><span>Avg Diff</span><b>{escape(_fmt_num(h.get('recent_diff_pg'), signed=True))}</b></div>
  </div>
  <div class="gt168-center-card">
    <div class="gt168-center-title">TREND</div>
    <div class="gt168-trends">
      <div class="gt168-trend {'bad' if a_trend == 'Slipping' else ''}"><b>{escape(a_trend)}</b><span>{escape(_clean(a.get('trend_detail')) or '—')}</span></div>
      <div class="gt168-trend {'bad' if h_trend == 'Slipping' else ''}"><b>{escape(h_trend)}</b><span>{escape(_clean(h.get('trend_detail')) or '—')}</span></div>
    </div>
  </div>
  <div class="gt168-center-card gt168-takeaways" data-testid="gt168-step3-takeaways"><h4>💡 KEY TAKEAWAYS</h4>{takeaway_html}</div>
</div>"""

    return f"""
<details class="gt159-step gt168-step3 {state_css}" data-testid="gt157-step-3" data-step3-state="{escape(state)}" open>
  <summary>
    <span class="gt159-num">3</span>
    <span class="gt159-stepcopy"><b>Current Form &amp; Opponent Quality</b><span>{escape(subtitle)}</span></span>
    <span class="gt159-state {state_css}">{escape(state)}</span>
  </summary>
  <div class="gt159-stepbody gt168-body">
    <div class="gt168-grid">{_team_card(a, home_side=False)}{center}{_team_card(h, home_side=True)}</div>
    <div class="gt168-edge" data-testid="gt168-step3-edge"><strong>▣ FORM EDGE</strong><span>{escape(_clean(contract['edge_label']))}</span><small>{escape(_clean(contract['edge_reason']))}</small></div>
  </div>
</details>"""


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP3_ADVANCED_FIELDS",
    "STEP3_CSS",
    "STEP3_PRESENTATION_MARKER",
    "STEP3_MIN_OPPONENT_QUALITY_COVERAGE",
    "STEP3_RUNTIME_SNAPSHOT_PATH",
    "STEP3_REQUIRED_FIELDS",
    "build_step3_contract",
    "enrich_step3_inputs",
    "build_team_form_contract",
    "render_step3_html",
    "_scoreboard_range_rows_for_team",
    "_apply_scoreboard_quality",
    "_scoreboard_quality_universe",
    "_scoreboard_range_events",
]
