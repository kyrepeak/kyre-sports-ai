"""Universal presentation-only Step 3 Current Form & Opponent Quality.

Step 3 answers one question for every future CFB Game Total matchup:
"Who is playing better lately, and how trustworthy is that form given the
quality of opponents faced?"

This module is display-only. It consumes already-reconciled evidence and never
changes projection, distribution, qualification, ranking, sportsbook, API, or
model behavior.
"""
from __future__ import annotations

from html import escape
import re
from statistics import fmean
from typing import Any, Mapping

import cfb_over_under_deep_data_reconciliation_v1 as deep

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

STEP3_PRESENTATION_MARKER = "CFB_GAME_TOTAL_STEP3_CURRENT_FORM_OPPONENT_QUALITY_ACTIVE"

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
    if len(margins) < 2:
        return "Insufficient sample", None
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
    qualifying = [row for row in games if row.get("opponent_win_pct") is not None and float(row["opponent_win_pct"]) > 0.5]
    if not qualifying:
        return "", 0
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


def enrich_step3_inputs(
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
    game: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Fill missing Step 3 recent-form evidence from exact ESPN team IDs only."""
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

    for side in ("away", "home"):
        current = outputs[side]
        current_contract = build_team_form_contract(
            current,
            (identity.get(side) or {}) if isinstance(identity, Mapping) else {},
            side=side,
        )
        if current_contract.get("required_complete"):
            diag[side] = {"fallback_used": False, "reason": "core_recent_form_already_complete"}
            continue

        team_id = _exact_team_id(
            (identity.get(side) or {}) if isinstance(identity, Mapping) else {},
            current,
            game,
            side,
        )
        if not (team_id and season and cutoff is not None):
            diag[side] = {
                "fallback_used": False,
                "reason": "exact_team_id_or_date_unavailable",
                "team_id": team_id,
            }
            continue

        try:
            rows, hydration, attempts = deep._current_rows(
                team_id,
                season,
                cutoff,
                event_id,
            )
        except Exception as exc:
            rows, hydration, attempts = [], {}, [{
                "provider": f"ESPN exact team {team_id} current-season Step 3 fallback",
                "error": f"{type(exc).__name__}: {exc}"[:260],
            }]
        outputs[side] = _overlay_exact_rows(current, rows)
        diag[side] = {
            "fallback_used": bool(rows),
            "team_id": team_id,
            "rows": len(rows),
            "hydrated_opponents": int(hydration.get("fallback_resolved") or 0)
            if isinstance(hydration, Mapping) else 0,
            "attempts": attempts,
        }

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

    if missing_required:
        state = "DATA LIMITED"
    elif missing_advanced:
        state = "CHECK"
    else:
        state = "READY"

    wins = sum(1 for row in games if row.get("result") == "W")
    win_rate = wins / len(games) if games else 0.0
    form_score = float(recent_diff or 0.0) + win_rate * 10.0
    if avg_opp_pct is not None:
        form_score += (avg_opp_pct - 0.5) * 16.0

    contract["missing_required"] = missing_required
    contract["missing_advanced"] = missing_advanced
    contract["required_complete"] = not missing_required
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
    missing_html = ""
    if missing:
        readable = ", ".join(str(x).replace("_", " ").title() for x in missing)
        missing_html = f'<div class="gt168-missing">Still checking: {escape(readable)}</div>'
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
      <div class="gt168-trend {'bad' if a_trend == 'Slipping' else ''}"><b>{escape(a_trend)}</b><span>{escape(_clean(a.get('last5_record')) or '—')}</span></div>
      <div class="gt168-trend {'bad' if h_trend == 'Slipping' else ''}"><b>{escape(h_trend)}</b><span>{escape(_clean(h.get('last5_record')) or '—')}</span></div>
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
    "STEP3_REQUIRED_FIELDS",
    "build_step3_contract",
    "enrich_step3_inputs",
    "build_team_form_contract",
    "render_step3_html",
]
