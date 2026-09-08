"""MLB Moneyline V17.2 — Step 6 lineup strength + missing players.

Additive presentation/evidence wrapper over permanently frozen V17.1 Step 5L.
Pregame cards gain official posted-lineup quality plus missing-player context.
Live mode remains owned by frozen V17.1/V19 and is not altered here.

Evidence:
- Official MLB current batting order from the game feed
- Most recent prior completed official batting order for continuity comparison
- Official MLB active roster to distinguish "active but not starting" from
  "not on active roster"
- Current lineup weighted AVG/OPS by batting-order slot

No Moneyline probability, simulation, fair-odds, ranking, candidate selection,
or market math changes. Current-lineup quality is scored once; missing-player
context is descriptive and is not double-penalized.
"""
from __future__ import annotations

from html import escape
import json
import math
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st

import mlb_moneyline_hub_v171 as prior
import mlb_moneyline_hub_v170 as pregame
import slate_lineup_v204 as lineup_source

MODEL_VERSION = "V17.2 • MONEYLINE STEP 6 • LINEUP STRENGTH + MISSING PLAYERS"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v171"
FROZEN_PREGAME_PRESENTATION = "mlb_moneyline_hub_v170"
FROZEN_MODEL_CHAIN = pregame.FROZEN_MODEL_CHAIN
SEASON = pregame.SEASON

MIN_CONFIRMED_HITTERS = 9
MIN_USABLE_HITTERS = 7

_ORDER_WEIGHTS = (1.12, 1.09, 1.07, 1.05, 1.02, 1.00, 0.97, 0.94, 0.90)

_STEP6_CSS = r"""
<style>
.ml172-step6{grid-area:identity;margin-top:7px;padding:10px 11px;border:1px solid rgba(89,164,255,.28);border-radius:13px;background:linear-gradient(145deg,rgba(7,20,38,.96),rgba(9,17,27,.97));box-shadow:inset 3px 0 #55a5ff}
.ml172-step6-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml172-step6-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#9bcaff}
.ml172-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #536269;background:#1b252a;color:#d0dadf}
.ml172-grade.home{border-color:#31755d;background:#0b3025;color:#98e7bf}.ml172-grade.away{border-color:#4e64a1;background:#111d3c;color:#abc2ff}.ml172-grade.neutral{border-color:#75621e;background:#31290d;color:#f4dc78}.ml172-grade.limited{border-color:#5a626a;background:#22292f;color:#d2dbe1}
.ml172-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.ml172-side{border:1px solid rgba(89,164,255,.18);border-radius:10px;background:rgba(8,18,28,.80);padding:8px}.ml172-side.home{text-align:right}.ml172-side h4{margin:0 0 3px;color:#f2f7f8;font-size:.65rem}.ml172-side small{color:#718890;font-size:.44rem}
.ml172-score{display:inline-flex;margin-top:5px;border-radius:999px;padding:4px 7px;border:1px solid #4f6b88;background:#122131;color:#bad8f6;font-size:.45rem;font-weight:900}.ml172-score.strong{border-color:#34775d;background:#0d3025;color:#9ce9c1}.ml172-score.average{border-color:#75621e;background:#30290d;color:#f4dc78}.ml172-score.weak{border-color:#70484a;background:#30191b;color:#f0b0b3}.ml172-score.limited{border-color:#555e65;background:#20272c;color:#c8d0d5}
.ml172-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.ml172-stat{border:1px solid rgba(91,140,166,.16);border-radius:8px;padding:6px 4px;background:#091722;text-align:center}.ml172-stat b{display:block;color:#e8f0f4;font-size:.57rem}.ml172-stat span{display:block;color:#718592;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml172-missing{margin-top:7px;border:1px solid rgba(89,164,255,.14);border-radius:8px;padding:6px 7px;background:#0b1723;color:#aab9c4;font-size:.45rem;line-height:1.42}.ml172-missing b{color:#dce8ef}
.ml172-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.ml172-pill{display:inline-flex;border-radius:999px;padding:4px 7px;border:1px solid rgba(89,164,255,.22);background:#101f30;color:#bcd7f4;font-size:.46rem;font-weight:850}.ml172-source{margin-top:6px;color:#708696;font-size:.43rem;line-height:1.4}
@media(max-width:640px){.ml172-grid{grid-template-columns:1fr}.ml172-side.home{text-align:left}.ml172-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.ml172-step6{padding:9px}}
</style>
"""


def _f(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None


def _rate(value: Any) -> float | None:
    val = _f(value)
    if val is None:
        return None
    if val > 2.0:
        val /= 1000.0
    return max(0.0, val)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _json(url: str) -> dict[str, Any] | None:
    try:
        req = Request(url, headers={"User-Agent": "KyreSportsAI/17.2"})
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def _active_roster(team_id: int, day: str) -> dict[str, Any]:
    query = urlencode({"rosterType": "active", "date": str(day)[:10]})
    data = _json(f"https://statsapi.mlb.com/api/v1/teams/{int(team_id)}/roster?{query}")
    if not data:
        return {"status": "PENDING", "ids": set()}
    ids = set()
    for row in data.get("roster") or []:
        pid = _i(((row.get("person") or {}).get("id")))
        if pid:
            ids.add(pid)
    return {"status": "VERIFIED" if ids else "PENDING", "ids": ids}


def _weighted_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    usable = []
    for row in rows[:9]:
        avg = _rate(row.get("avg"))
        ops = _rate(row.get("ops"))
        spot = _i(row.get("spot")) or (len(usable) + 1)
        if avg is None or ops is None or spot < 1 or spot > 9:
            continue
        usable.append((avg, ops, _ORDER_WEIGHTS[spot - 1]))
    if not usable:
        return {"usable": 0, "weighted_avg": None, "weighted_ops": None}
    denom = sum(w for _, _, w in usable)
    return {
        "usable": len(usable),
        "weighted_avg": sum(avg * w for avg, _, w in usable) / denom,
        "weighted_ops": sum(ops * w for _, ops, w in usable) / denom,
    }


def _lineup_score(metrics: Mapping[str, Any], confirmed_count: int) -> dict[str, Any]:
    avg = _f(metrics.get("weighted_avg"))
    ops = _f(metrics.get("weighted_ops"))
    usable = int(metrics.get("usable") or 0)
    if confirmed_count < MIN_CONFIRMED_HITTERS or usable < MIN_USABLE_HITTERS or avg is None or ops is None:
        return {"score": None, "label": "DATA LIMITED / PENDING", "label_cls": "limited"}

    ops_signal = _clamp((ops - 0.720) / 0.160, -1.0, 1.0)
    avg_signal = _clamp((avg - 0.245) / 0.050, -1.0, 1.0)
    signal = 0.72 * ops_signal + 0.28 * avg_signal
    score = int(round(_clamp(50.0 + 25.0 * signal, 25.0, 75.0)))

    if score >= 64:
        label, cls = "ELITE LINEUP", "strong"
    elif score >= 57:
        label, cls = "STRONG LINEUP", "strong"
    elif score >= 44:
        label, cls = "AVERAGE LINEUP", "average"
    elif score >= 36:
        label, cls = "WEAK LINEUP", "weak"
    else:
        label, cls = "VERY WEAK LINEUP", "weak"
    return {"score": score, "label": label, "label_cls": cls}


def _missing_context(current: list[Mapping[str, Any]], previous: list[Mapping[str, Any]], active_ids: set[int] | None) -> dict[str, Any]:
    current_ids = {_i(row.get("player_id")) for row in current}
    current_ids.discard(None)
    previous_map = {
        _i(row.get("player_id")): dict(row)
        for row in previous
        if _i(row.get("player_id")) is not None
    }
    missing = [row for pid, row in previous_map.items() if pid not in current_ids]
    additions = [dict(row) for row in current if _i(row.get("player_id")) not in previous_map]

    inactive = []
    active_not_starting = []
    for row in missing:
        pid = _i(row.get("player_id"))
        if active_ids is None:
            continue
        if pid in active_ids:
            active_not_starting.append(row)
        else:
            inactive.append(row)

    return {
        "missing": missing,
        "additions": additions,
        "inactive": inactive,
        "active_not_starting": active_not_starting,
    }


def _names(rows: list[Mapping[str, Any]], limit: int = 3) -> str:
    names = [str(row.get("player_name") or "Unknown") for row in rows[:limit]]
    if len(rows) > limit:
        names.append(f"+{len(rows)-limit} more")
    return ", ".join(names) if names else "None"


def _team_context(
    team_id: Any,
    team_name: Any,
    current: list[Mapping[str, Any]],
    previous: list[Mapping[str, Any]],
    roster: Mapping[str, Any],
) -> dict[str, Any]:
    current_metrics = _weighted_metrics(current)
    previous_metrics = _weighted_metrics(previous)
    graded = _lineup_score(current_metrics, len(current))

    active_ids = set(roster.get("ids") or []) if roster.get("status") == "VERIFIED" else None
    missing = _missing_context(current, previous, active_ids)

    current_ops = _f(current_metrics.get("weighted_ops"))
    previous_ops = _f(previous_metrics.get("weighted_ops"))
    continuity_delta = (
        current_ops - previous_ops
        if current_ops is not None and previous_ops is not None and len(previous) >= 9
        else None
    )

    quality = 0
    quality += 40 if len(current) >= 9 else int(round(40 * _clamp(len(current) / 9.0, 0.0, 1.0)))
    quality += 30 if int(current_metrics.get("usable") or 0) >= 7 else int(round(30 * _clamp(int(current_metrics.get("usable") or 0) / 7.0, 0.0, 1.0)))
    quality += 15 if len(previous) >= 9 else 0
    quality += 15 if roster.get("status") == "VERIFIED" else 0

    reason = ""
    if len(current) < 9:
        reason = "Official batting order is not fully posted."
    elif int(current_metrics.get("usable") or 0) < 7:
        reason = "Too few posted hitters have usable official AVG/OPS evidence."
    elif len(previous) < 9:
        reason = "Prior official lineup unavailable; missing-player continuity is partial."
    elif roster.get("status") != "VERIFIED":
        reason = "Active-roster status unavailable; missing-player availability classification is partial."

    return {
        "team_id": _i(team_id),
        "team_name": str(team_name or "Team"),
        "confirmed_count": len(current),
        "metrics": current_metrics,
        "previous_metrics": previous_metrics,
        "score": graded.get("score"),
        "label": graded.get("label"),
        "label_cls": graded.get("label_cls"),
        "quality": quality,
        "continuity_delta": continuity_delta,
        "missing": missing,
        "roster_status": roster.get("status"),
        "reason": reason,
    }


def _build_context(rows: Mapping[int, Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    if not rows:
        return {}

    pks = tuple(sorted(int(pk) for pk in rows if _i(pk)))
    try:
        current_lineups = lineup_source._fetch_lineups_bulk(pks)
    except Exception:
        current_lineups = {}

    first = next(iter(rows.values()))
    day = str(first.get("game_date") or "")[:10]
    team_ids = []
    for row in rows.values():
        for key in ("away_team_id", "home_team_id"):
            tid = _i(row.get(key))
            if tid:
                team_ids.append(tid)

    try:
        recent = lineup_source._recent_team_games(day, tuple(sorted(set(team_ids)))) if day else {}
    except Exception:
        recent = {}

    prior_pks = tuple(sorted({
        int(item.get("game_pk"))
        for item in recent.values()
        if _i(item.get("game_pk"))
    }))
    try:
        prior_lineups = lineup_source._fetch_lineups_bulk(prior_pks) if prior_pks else {}
    except Exception:
        prior_lineups = {}

    rosters = {}
    for tid in sorted(set(team_ids)):
        rosters[tid] = _active_roster(tid, day) if day else {"status": "PENDING", "ids": set()}

    out: dict[int, dict[str, Any]] = {}
    for pk, row in rows.items():
        current = current_lineups.get(int(pk)) or {"away": [], "home": []}
        item = {}
        for side in ("away", "home"):
            tid = _i(row.get(f"{side}_team_id"))
            prev_meta = recent.get(tid) if tid else None
            previous = []
            if prev_meta and _i(prev_meta.get("game_pk")):
                previous = (
                    (prior_lineups.get(int(prev_meta["game_pk"])) or {}).get(str(prev_meta.get("side") or side))
                    or []
                )
            item[side] = _team_context(
                tid,
                row.get(f"{side}_team") or row.get(f"{side}_name"),
                list(current.get(side) or []),
                list(previous or []),
                rosters.get(tid) or {"status": "PENDING", "ids": set()},
            )
        out[int(pk)] = item
    return out


def _overall_grade(away: Mapping[str, Any], home: Mapping[str, Any]) -> tuple[str, str, float | None]:
    a = _f(away.get("score"))
    h = _f(home.get("score"))
    if a is None or h is None:
        return "DATA LIMITED / PENDING", "limited", None
    edge = h - a
    if edge >= 10:
        return "STRONG HOME LINEUP EDGE", "home", edge
    if edge >= 4:
        return "HOME LINEUP EDGE", "home", edge
    if edge <= -10:
        return "STRONG AWAY LINEUP EDGE", "away", edge
    if edge <= -4:
        return "AWAY LINEUP EDGE", "away", edge
    return "LINEUPS CLOSE", "neutral", edge


def _fmt(value: Any, digits: int = 3, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.{digits}f}{suffix}"


def _side_html(side: Mapping[str, Any], home: bool = False) -> str:
    m = side.get("metrics") or {}
    missing = side.get("missing") or {}
    score = side.get("score")
    score_text = "N/A" if score is None else f"{int(score)}/100"
    delta = side.get("continuity_delta")
    delta_text = "N/A" if delta is None else f"{float(delta):+.3f}"

    return (
        f'<div class="ml172-side {"home" if home else ""}">'
        f'<h4>{escape(str(side.get("team_name") or "Team"))}</h4>'
        f'<small>{int(side.get("confirmed_count") or 0)}/9 official hitters posted</small>'
        f'<div class="ml172-score {escape(str(side.get("label_cls") or "limited"))}">{escape(str(side.get("label") or "DATA LIMITED / PENDING"))} • {escape(score_text)}</div>'
        '<div class="ml172-stats">'
        f'<div class="ml172-stat"><b>{_fmt(m.get("weighted_avg"))}</b><span>Weighted AVG</span></div>'
        f'<div class="ml172-stat"><b>{_fmt(m.get("weighted_ops"))}</b><span>Weighted OPS</span></div>'
        f'<div class="ml172-stat"><b>{int(m.get("usable") or 0)}</b><span>Usable hitters</span></div>'
        f'<div class="ml172-stat"><b>{escape(delta_text)}</b><span>OPS vs prior lineup</span></div>'
        '</div>'
        '<div class="ml172-missing">'
        f'<b>Missing vs prior official lineup:</b> {len(missing.get("missing") or [])} • {_names(missing.get("missing") or [])}<br>'
        f'<b>Not on active roster:</b> {len(missing.get("inactive") or [])} • {_names(missing.get("inactive") or [])}<br>'
        f'<b>Active, not starting:</b> {len(missing.get("active_not_starting") or [])} • {_names(missing.get("active_not_starting") or [])}'
        '</div>'
        f'<div class="ml172-source">Data quality {int(side.get("quality") or 0)}/100. Missing-player context is descriptive only; current lineup quality already reflects replacements, so no second penalty is applied. {escape(str(side.get("reason") or ""))}</div>'
        '</div>'
    )


def _html(context: Mapping[str, Any]) -> str:
    away = context.get("away") or {}
    home = context.get("home") or {}
    grade, grade_cls, edge = _overall_grade(away, home)
    edge_text = "N/A" if edge is None else f"{abs(float(edge)):.1f} pts"
    return (
        '<div class="ml172-step6">'
        '<div class="ml172-step6-head">'
        '<span class="ml172-step6-title">STEP 6 • LINEUP STRENGTH + MISSING PLAYERS</span>'
        f'<span class="ml172-grade {escape(grade_cls)}">{escape(grade)}</span>'
        '</div>'
        '<div class="ml172-grid">'
        f'{_side_html(away, False)}'
        f'{_side_html(home, True)}'
        '</div>'
        '<div class="ml172-pills">'
        f'<span class="ml172-pill">LINEUP DIFFERENTIAL • {escape(edge_text)}</span>'
        '<span class="ml172-pill">OFFICIAL POSTED ORDER</span>'
        '<span class="ml172-pill">NO DOUBLE PENALTY</span>'
        '<span class="ml172-pill">NO PROBABILITY ADJUSTMENT</span>'
        '</div>'
        '<div class="ml172-source">Official MLB batting orders + previous completed official lineup + active roster. "Not on active roster" is not automatically labeled as injured.</div>'
        '</div>'
    )


def _inject(card: str, html: str) -> str:
    text = str(card or "")
    if not html or "ks-pick-card" not in text or "ml172-step6" in text:
        return text
    return text[:-6] + html + "</div>" if text.endswith("</div>") else text + html


_FROZEN_STEP5_RENDERER = pregame._renderer


def _renderer(original, rows, lineups):
    step5 = _FROZEN_STEP5_RENDERER(original, rows, lineups)
    contexts = _build_context(rows)

    def wrapped(results, status_info, team_logo, h):
        ordered = list(results or [])[:5]
        cursor = {"i": 0}
        original_markdown = st.markdown

        def capture(body: Any, *args: Any, **kwargs: Any):
            text = str(body or "")
            if "ks-pick-card" in text and cursor["i"] < len(ordered):
                result = ordered[cursor["i"]]
                cursor["i"] += 1
                pk = _i(result.get("game_pk"))
                text = _inject(text, _html(contexts.get(pk) or {}))
            return original_markdown(text, *args, **kwargs)

        st.markdown = capture
        try:
            return step5(results, status_info, team_logo, h)
        finally:
            st.markdown = original_markdown

    return wrapped


def _render_pregame_with_step6(games_df, section_header, status_info, team_logo, h):
    original_renderer = pregame._renderer
    pregame._renderer = _renderer
    try:
        return pregame.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        pregame._renderer = original_renderer


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Preserve frozen Step 5L live mode while extending only its pregame path."""
    st.markdown(_STEP6_CSS, unsafe_allow_html=True)
    original_pregame = prior._render_pregame
    prior._render_pregame = _render_pregame_with_step6
    try:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior._render_pregame = original_pregame


__all__ = [
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "FROZEN_PREGAME_PRESENTATION",
    "MIN_CONFIRMED_HITTERS",
    "MIN_USABLE_HITTERS",
    "MODEL_VERSION",
    "_active_roster",
    "_build_context",
    "_lineup_score",
    "_missing_context",
    "_overall_grade",
    "_weighted_metrics",
    "render_moneyline_hub",
]
