"""MLB 1+ Hit UI V13.13 — Step 10 starter workload + times-through-order context.

Presentation/context-only wrapper around verified V13.12. Hit Model V13 probability
math, Monte Carlo, candidate pool, lineup handling, ranking, calibration and
persistence remain unchanged.

Step 10 adds official MLB starting-pitcher workload context for each Top-5 card:
1) season pitches/start, batters faced/start and innings/start,
2) date-cut recent-start workload before the selected slate,
3) days of rest since the most recent prior start,
4) a transparent times-through-the-order reach summary based on official BF/start
   and the hitter's batting-order slot,
5) the existing native V13 starter-share translated into display-only projected PA
   against the starter, and
6) a descriptive hook/deep-start heuristic. No workload label is an official team
   decision and no Step-10 field enters the V13 model or ranking.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math

import requests
import streamlit as st

import engine as hit_engine
import mlb_hit_hub_v1312 as prior

active = prior.active
core = prior.core
visual = prior.visual

UI_VERSION = "V13.13"
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}

# Cache-safe boundary: preserve verified Steps 1-9 exactly by name.
_BASE_PICK_HTML = prior._pick_html_v1312


def _safe_id(value):
    return prior._safe_id(value)


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _selected_day():
    try:
        return str(prior._selected_day() or "")[:10]
    except Exception:
        return ""


def _season_from_day():
    day = _selected_day()
    try:
        return datetime.strptime(day, "%Y-%m-%d").year
    except Exception:
        try:
            return int(hit_engine.season())
        except Exception:
            return 2026


def _fmt(value, digits=1):
    x = _num(value, None)
    return "—" if x is None else f"{x:.{digits}f}"


def _pct(value, digits=1):
    x = _num(value, None)
    return "—" if x is None else f"{x * 100.0:.{digits}f}%"


def _ip(value):
    try:
        return float(hit_engine.ipfloat(value))
    except Exception:
        return _num(value, None)


@st.cache_data(ttl=1200, show_spinner=False)
def _starter_season_context(starter_id, season_year):
    pid = _safe_id(starter_id)
    if pid is None:
        return {"available": False}
    try:
        r = requests.get(
            f"{MLB_API}/people/{pid}/stats",
            params={"stats": "season", "group": "pitching", "season": int(season_year), "gameType": "R"},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        split = ((groups[0].get("splits") or [None])[0] if groups else None) or {}
        stat = split.get("stat") or {}
        starts = int(_num(stat.get("gamesStarted"), 0) or 0)
        if starts <= 0:
            return {"available": False}
        bf = _num(stat.get("battersFaced"), None)
        pitches = _num(stat.get("numberOfPitches"), None)
        innings = _ip(stat.get("inningsPitched"))
        return {
            "available": True,
            "starts": starts,
            "pitches_per_start": (pitches / starts) if pitches is not None else None,
            "bf_per_start": (bf / starts) if bf is not None else None,
            "ip_per_start": (innings / starts) if innings is not None else None,
        }
    except Exception:
        return {"available": False}


@st.cache_data(ttl=1200, show_spinner=False)
def _starter_recent_starts(starter_id, season_year, slate_day):
    """Official MLB game-log starts strictly before the selected slate date."""
    pid = _safe_id(starter_id)
    try:
        slate = datetime.strptime(str(slate_day)[:10], "%Y-%m-%d").date()
    except Exception:
        return {"available": False, "starts": []}
    if pid is None:
        return {"available": False, "starts": []}

    try:
        r = requests.get(
            f"{MLB_API}/people/{pid}/stats",
            params={"stats": "gameLog", "group": "pitching", "season": int(season_year), "gameType": "R"},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
    except Exception:
        return {"available": False, "starts": []}

    rows = []
    for group in groups:
        for split in group.get("splits") or []:
            stat = (split or {}).get("stat") or {}
            started = int(_num(stat.get("gamesStarted"), 0) or 0)
            if started <= 0:
                continue
            date_text = str((split or {}).get("date") or ((split or {}).get("game") or {}).get("gameDate") or "")[:10]
            try:
                gday = datetime.strptime(date_text, "%Y-%m-%d").date()
            except Exception:
                continue
            if gday >= slate:
                continue
            rows.append({
                "date": gday,
                "pitches": _num(stat.get("numberOfPitches"), _num(stat.get("pitchesThrown"), None)),
                "bf": _num(stat.get("battersFaced"), None),
                "ip": _ip(stat.get("inningsPitched")),
            })

    rows.sort(key=lambda x: x["date"], reverse=True)
    rows = rows[:5]
    if not rows:
        return {"available": False, "starts": []}

    def avg(key):
        vals = [_num(r.get(key), None) for r in rows]
        vals = [v for v in vals if v is not None]
        return (sum(vals) / len(vals)) if vals else None

    return {
        "available": True,
        "starts": rows,
        "avg_pitches": avg("pitches"),
        "avg_bf": avg("bf"),
        "avg_ip": avg("ip"),
        "days_rest": (slate - rows[0]["date"]).days if rows else None,
    }


def _projected_pa_and_share(result):
    expected_ab = _num((result or {}).get("expected_ab"), None)
    spot = int(_num((result or {}).get("position"), 0) or 0)
    if expected_ab is None:
        try:
            expected_ab = float(hit_engine.ab_for_spot(spot))
        except Exception:
            expected_ab = None

    projected_pa = None
    pid = _safe_id((result or {}).get("player_id"))
    if pid is not None and expected_ab is not None:
        try:
            h = hit_engine.hitter_stats(pid) or {}
            pa = _num(h.get("plate_appearances"), None)
            ab = _num(h.get("at_bats"), None)
            if pa is not None and ab is not None and pa > 0 and ab > 0:
                ratio = max(1.0, min(pa / ab, 1.45))
                projected_pa = max(3.0, min(expected_ab * ratio, 6.5))
        except Exception:
            projected_pa = None

    pitcher = (result or {}).get("pitcher") or {}
    if not pitcher:
        sid = _safe_id((result or {}).get("starter_id"))
        if sid is not None:
            try:
                pitcher = hit_engine.pitcher_stats(sid) or {}
            except Exception:
                pitcher = {}
    share = None
    if expected_ab is not None:
        try:
            share = _num((hit_engine.starter_exposure(pitcher, expected_ab) or {}).get("starter_share"), None)
        except Exception:
            share = None
    return projected_pa, share


def _tto_reach(spot, bf_per_start):
    if not spot or bf_per_start is None:
        return "UNAVAILABLE"
    thresholds = [(1, spot), (2, spot + 9), (3, spot + 18), (4, spot + 27)]
    reached = [label for label, threshold in thresholds if bf_per_start >= threshold]
    if not reached:
        return "TTO1 not guaranteed by season BF/start"
    return "Season BF/start reaches " + " / ".join(f"TTO{x}" for x in reached)


def _hook_profile(season_ctx, recent_ctx):
    recent_ip = _num(recent_ctx.get("avg_ip"), None)
    recent_p = _num(recent_ctx.get("avg_pitches"), None)
    season_ip = _num(season_ctx.get("ip_per_start"), None)
    season_p = _num(season_ctx.get("pitches_per_start"), None)

    ip_ref = recent_ip if recent_ip is not None else season_ip
    p_ref = recent_p if recent_p is not None else season_p
    if ip_ref is None and p_ref is None:
        return "WORKLOAD PROFILE UNAVAILABLE"
    if (ip_ref is not None and ip_ref < 5.0) or (p_ref is not None and p_ref < 80):
        return "EARLIER-HOOK WATCH"
    if (ip_ref is not None and ip_ref >= 5.8) and (p_ref is None or p_ref >= 90):
        return "DEEPER-START LEAN"
    return "NORMAL STARTER DEPTH"


def _starter_workload_strip(result):
    season = _season_from_day()
    slate = _selected_day()
    sid = _safe_id((result or {}).get("starter_id"))
    starter_name = str((result or {}).get("starter_name") or ((result or {}).get("pitcher") or {}).get("name") or "Opposing starter")
    spot = int(_num((result or {}).get("position"), 0) or 0)

    season_ctx = _starter_season_context(sid, season)
    recent_ctx = _starter_recent_starts(sid, season, slate)
    projected_pa, starter_share = _projected_pa_and_share(result)

    if not season_ctx.get("available") and not recent_ctx.get("available"):
        return (
            '<div class="hit1313-context">'
            '<div class="hit1313-head">STEP 10 • STARTER WORKLOAD + TIMES-THROUGH-ORDER</div>'
            '<div class="hit1313-note">Official prior-start workload unavailable for this starter. No hook or TTO value was invented; V13 ranking is unaffected.</div>'
            '</div>'
        )

    season_bits = []
    if season_ctx.get("available"):
        season_bits.append(f"{int(season_ctx.get('starts') or 0)} starts")
        if _num(season_ctx.get("pitches_per_start"), None) is not None:
            season_bits.append(f"{_fmt(season_ctx.get('pitches_per_start'), 1)} pitches/start")
        if _num(season_ctx.get("bf_per_start"), None) is not None:
            season_bits.append(f"{_fmt(season_ctx.get('bf_per_start'), 1)} BF/start")
        if _num(season_ctx.get("ip_per_start"), None) is not None:
            season_bits.append(f"{_fmt(season_ctx.get('ip_per_start'), 1)} IP/start")

    recent_bits = []
    if recent_ctx.get("available"):
        if _num(recent_ctx.get("avg_pitches"), None) is not None:
            recent_bits.append(f"L5 {_fmt(recent_ctx.get('avg_pitches'), 1)} pitches")
        if _num(recent_ctx.get("avg_bf"), None) is not None:
            recent_bits.append(f"{_fmt(recent_ctx.get('avg_bf'), 1)} BF")
        if _num(recent_ctx.get("avg_ip"), None) is not None:
            recent_bits.append(f"{_fmt(recent_ctx.get('avg_ip'), 1)} IP")
        if _num(recent_ctx.get("days_rest"), None) is not None:
            recent_bits.append(f"{int(recent_ctx.get('days_rest'))} days since prior start")

    exposure_bits = []
    if starter_share is not None:
        exposure_bits.append(f"V13 starter share {_pct(starter_share)}")
    if projected_pa is not None and starter_share is not None:
        exposure_bits.append(f"~{_fmt(projected_pa * starter_share, 1)} projected PA vs SP")

    bf_ref = _num(recent_ctx.get("avg_bf"), None) if recent_ctx.get("available") else None
    if bf_ref is None:
        bf_ref = _num(season_ctx.get("bf_per_start"), None)
    tto_text = _tto_reach(spot, bf_ref)
    hook = _hook_profile(season_ctx, recent_ctx)

    starts_html = []
    for row in (recent_ctx.get("starts") or [])[:3]:
        bits = [row["date"].strftime("%b %d")]
        if _num(row.get("pitches"), None) is not None:
            bits.append(f"{int(round(row.get('pitches')))}p")
        if _num(row.get("bf"), None) is not None:
            bits.append(f"{int(round(row.get('bf')))} BF")
        if _num(row.get("ip"), None) is not None:
            bits.append(f"{_fmt(row.get('ip'), 1)} IP")
        starts_html.append(" • ".join(bits))

    return (
        '<div class="hit1313-context">'
        '<div class="hit1313-head">STEP 10 • STARTER WORKLOAD + TIMES-THROUGH-ORDER</div>'
        f'<div class="hit1313-main"><b>{escape(starter_name)}</b> • {escape(" • ".join(season_bits) if season_bits else "season workload unavailable")}</div>'
        f'<div class="hit1313-sub"><b>Recent starts</b> • {escape(" • ".join(recent_bits) if recent_bits else "date-cut L5 workload unavailable")}</div>'
        f'<div class="hit1313-sub"><b>Hitter exposure</b> • {escape(" • ".join(exposure_bits) if exposure_bits else "starter-share PA estimate unavailable")}</div>'
        f'<div class="hit1313-tto"><b>{escape(hook)}</b> • {escape(tto_text)}</div>'
        + (f'<div class="hit1313-recent">Prior starts: {escape(" | ".join(starts_html))}</div>' if starts_html else '') +
        '<div class="hit1313-note">TTO reach and hook labels are transparent workload heuristics from official prior MLB workload only. They are not manager decisions and do not change Hit Model V13.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hit1313-context{margin:7px 0 5px;padding:9px 10px;border:1px solid #5a4d72;background:linear-gradient(145deg,#171221,#0b111b);border-radius:12px}
.hit1313-head{font-size:.44rem;letter-spacing:.08em;color:#c8a9ff;font-weight:950;text-transform:uppercase}
.hit1313-main{font-size:.53rem;color:#edf1f7;line-height:1.48;margin-top:3px}.hit1313-main b{color:#f2e8ff}
.hit1313-sub{font-size:.49rem;color:#c7d0dc;line-height:1.46;margin-top:3px}.hit1313-sub b{color:#e3d8f5}
.hit1313-tto{font-size:.50rem;color:#d9c8e9;line-height:1.46;margin-top:4px}.hit1313-tto b{color:#e9c56c}
.hit1313-recent{font-size:.45rem;color:#aab6c6;line-height:1.42;margin-top:4px}
.hit1313-note{font-size:.40rem;color:#778292;line-height:1.4;margin-top:4px}
</style>
"""

if "hit1313-context" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v1313(result, rank):
    html = _BASE_PICK_HTML(result, rank)
    if not isinstance(html, str):
        html = str(html or "")
    try:
        strip = _starter_workload_strip(result if isinstance(result, dict) else {})
    except Exception:
        strip = (
            '<div class="hit1313-context">'
            '<div class="hit1313-head">STEP 10 • STARTER WORKLOAD + TIMES-THROUGH-ORDER</div>'
            '<div class="hit1313-note">Step-10 context unavailable for this card. V13 projection and ranking remain unaffected.</div>'
            '</div>'
        )
    marker = '<div class="hit-pick-prob">'
    if marker in html:
        return html.replace(marker, strip + marker, 1)
    return html + strip


active._pick_html = _pick_html_v1313


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🧠 Hit UI V13.13 • Step 10 starter workload + times-through-order context ACTIVE • "
        "official MLB date-cut workload • display/context only • Hit Model V13 unchanged"
    )
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
