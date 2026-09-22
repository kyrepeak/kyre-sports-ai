"""MLB 1+ Hit UI V13.9 — Step 6 plate-appearance opportunity context.

Presentation/context-only wrapper around verified V13.8. Hit Model V13 probability
math, Monte Carlo, candidate pool, lineup handling, ranking, calibration and
persistence remain unchanged.

Step 6 adds display-only opportunity context for each Top-5 hitter:
1) confirmed/projected batting-order slot and home/away side,
2) the frozen V13 expected-at-bats value,
3) a display-only projected-PA estimate derived from V13 expected AB × the hitter's
   official MLB season PA/AB ratio,
4) official MLB team season PA/game and runs/game context,
5) the native V13 starter-vs-bullpen exposure split expressed as projected PA,
6) official MLB starter batters-faced-per-start when available,
7) a structural bottom-9 availability note for home hitters, and
8) a transparent substitution-risk heuristic based only on lineup confirmation and
   batting-order slot.

No Step-6 field is passed into prescreen, deep_scan, model_inputs, Monte Carlo,
confidence, calibration or ranking. Missing values are labeled unavailable rather
than invented.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

import requests
import streamlit as st

import engine as hit_engine
import mlb_hit_hub_v138 as prior

active = prior.active
core = prior.core
visual = prior.visual

UI_VERSION = "V13.9"
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}

# Preserve verified Steps 1-5 exactly; Step 6 only injects one additional card block.
_BASE_PICK_HTML = active._pick_html


def _safe_id(value):
    return prior._safe_id(value)


def _sf(value, default=None):
    return prior._sf(value, default)


def _selected_day():
    return prior._selected_day()


def _season_from_day():
    try:
        return datetime.strptime(_selected_day(), "%Y-%m-%d").year
    except Exception:
        return hit_engine.season()


def _fmt(value, digits=1):
    x = _sf(value, None)
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def _pct(value, digits=1):
    x = _sf(value, None)
    if x is None:
        return "—"
    return f"{x * 100.0:.{digits}f}%"


@st.cache_data(ttl=900, show_spinner=False)
def _team_season_opportunity(team_id, season):
    """Official MLB team season hitting totals converted to per-game context."""
    tid = _safe_id(team_id)
    if tid is None:
        return {"available": False}
    try:
        r = requests.get(
            f"{MLB_API}/teams/{tid}/stats",
            params={"stats": "season", "group": "hitting", "season": int(season)},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        split = ((groups[0].get("splits") or [None])[0] if groups else None) or {}
        stat = split.get("stat") or {}
        games = _sf(stat.get("gamesPlayed"), 0) or 0
        pa = _sf(stat.get("plateAppearances"), None)
        ab = _sf(stat.get("atBats"), None)
        runs = _sf(stat.get("runs"), None)
        if games <= 0:
            return {"available": False}
        return {
            "available": True,
            "games": int(games),
            "pa_per_game": (pa / games) if pa is not None else None,
            "ab_per_game": (ab / games) if ab is not None else None,
            "runs_per_game": (runs / games) if runs is not None else None,
        }
    except Exception:
        return {"available": False}


@st.cache_data(ttl=900, show_spinner=False)
def _starter_workload_context(starter_id, season):
    """Official MLB starter season BF/start context; display-only."""
    pid = _safe_id(starter_id)
    if pid is None:
        return {"available": False}
    try:
        r = requests.get(
            f"{MLB_API}/people/{pid}/stats",
            params={"stats": "season", "group": "pitching", "season": int(season)},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        split = ((groups[0].get("splits") or [None])[0] if groups else None) or {}
        stat = split.get("stat") or {}
        starts = _sf(stat.get("gamesStarted"), 0) or 0
        bf = _sf(stat.get("battersFaced"), None)
        innings = hit_engine.ipfloat(stat.get("inningsPitched"))
        if starts <= 0:
            return {"available": False}
        return {
            "available": True,
            "starts": int(starts),
            "bf_per_start": (bf / starts) if bf is not None else None,
            "ip_per_start": (innings / starts) if innings is not None else None,
        }
    except Exception:
        return {"available": False}


def _hitter_pa_projection(result, expected_ab):
    """Display estimate only: V13 expected AB scaled by official season PA/AB."""
    pid = _safe_id(result.get("player_id"))
    if pid is None or expected_ab is None:
        return None, None
    try:
        stats = hit_engine.hitter_stats(pid) or {}
    except Exception:
        stats = {}
    pa = _sf(stats.get("plate_appearances"), None)
    ab = _sf(stats.get("at_bats"), None)
    if pa is None or ab is None or pa <= 0 or ab <= 0:
        return None, None
    ratio = max(1.0, min(pa / ab, 1.45))
    projected = max(3.0, min(float(expected_ab) * ratio, 6.5))
    return projected, ratio


def _exposure_context(result, expected_ab):
    pitcher = result.get("pitcher") or {}
    if not pitcher:
        sid = _safe_id(result.get("starter_id"))
        if sid is not None:
            try:
                pitcher = hit_engine.pitcher_stats(sid) or {}
            except Exception:
                pitcher = {}
    try:
        return hit_engine.starter_exposure(pitcher, expected_ab) or {}
    except Exception:
        return {}


def _substitution_note(result):
    confirmed = bool(result.get("lineup_confirmed"))
    spot = int(_sf(result.get("position"), 0) or 0)
    if not confirmed:
        return "UNKNOWN • projected lineup; substitution role is not inferred"
    if 1 <= spot <= 6:
        return "LOWER WATCH • confirmed top-6 starter; no pinch-hit penalty inferred"
    if 7 <= spot <= 9:
        return "WATCH • confirmed lower-order starter; substitution risk shown qualitatively only"
    return "UNKNOWN • lineup slot unavailable"


def _ninth_inning_note(result):
    side = str(result.get("team_side") or "").lower()
    if side == "home":
        return "PRESENT • home club can lose the bottom 9th when already leading"
    if side == "away":
        return "NONE STRUCTURAL • away club receives the top 9th in a regulation game"
    return "UNKNOWN • home/away side unavailable"


def _opportunity_strip(result):
    season = _season_from_day()
    spot = int(_sf(result.get("position"), 0) or 0)
    side = str(result.get("team_side") or "Unknown").upper()
    lineup = "CONFIRMED" if result.get("lineup_confirmed") else "PROJECTED"

    expected_ab = _sf(result.get("expected_ab"), None)
    if expected_ab is None:
        try:
            expected_ab = float(hit_engine.ab_for_spot(spot))
        except Exception:
            expected_ab = None

    projected_pa, pa_ab_ratio = _hitter_pa_projection(result, expected_ab)
    team_ctx = _team_season_opportunity(result.get("team_id"), season)
    starter_ctx = _starter_workload_context(result.get("starter_id"), season)
    exposure = _exposure_context(result, expected_ab or 4.1)

    headline_bits = [f"Bat #{spot if spot else '—'}", escape(side), lineup]
    if expected_ab is not None:
        headline_bits.append(f"V13 expected AB {_fmt(expected_ab, 1)}")
    if projected_pa is not None:
        headline_bits.append(f"display PA est. {_fmt(projected_pa, 1)}")

    if team_ctx.get("available"):
        team_bits = []
        if team_ctx.get("pa_per_game") is not None:
            team_bits.append(f"{_fmt(team_ctx.get('pa_per_game'), 1)} team PA/game")
        if team_ctx.get("runs_per_game") is not None:
            team_bits.append(f"{_fmt(team_ctx.get('runs_per_game'), 2)} R/game")
        team_text = " • ".join(team_bits) if team_bits else "Official team opportunity totals unavailable"
    else:
        team_text = "Official team season PA/game unavailable"

    exposure_bits = []
    share = _sf(exposure.get("starter_share"), None)
    if share is not None:
        exposure_bits.append(f"Starter share {_pct(share)}")
        exposure_bits.append(f"Bullpen share {_pct(1.0 - share)}")
        if projected_pa is not None:
            exposure_bits.append(f"~{_fmt(projected_pa * share, 1)} PA vs SP")
            exposure_bits.append(f"~{_fmt(projected_pa * (1.0 - share), 1)} PA vs BP")
    exposure_text = " • ".join(exposure_bits) if exposure_bits else "Starter/bullpen PA exposure unavailable"

    starter_bits = []
    if starter_ctx.get("available"):
        if starter_ctx.get("bf_per_start") is not None:
            starter_bits.append(f"{_fmt(starter_ctx.get('bf_per_start'), 1)} BF/start")
        if starter_ctx.get("ip_per_start") is not None:
            starter_bits.append(f"{_fmt(starter_ctx.get('ip_per_start'), 1)} IP/start")
    starter_text = " • ".join(starter_bits) if starter_bits else "Official starter BF/start unavailable"

    ratio_note = (
        f"PA estimate uses official season PA/AB ratio {_fmt(pa_ab_ratio, 3)} × frozen V13 expected AB; display only."
        if pa_ab_ratio is not None
        else "Projected PA unavailable; no PA/AB ratio was invented."
    )

    return (
        '<div class="hit139-context">'
        '<div class="hit139-head">STEP 6 • HIT OPPORTUNITY / PLATE-APPEARANCE CONTEXT</div>'
        f'<div class="hit139-main">{" • ".join(headline_bits)}</div>'
        f'<div class="hit139-sub"><b>Team opportunity</b> • {team_text}</div>'
        f'<div class="hit139-sub"><b>Starter / bullpen exposure</b> • {exposure_text}</div>'
        f'<div class="hit139-sub"><b>Opposing starter workload</b> • {starter_text}</div>'
        '<div class="hit139-divider"></div>'
        f'<div class="hit139-risk"><b>Bottom-9 availability:</b> {escape(_ninth_inning_note(result))}</div>'
        f'<div class="hit139-risk"><b>Substitution watch:</b> {escape(_substitution_note(result))}</div>'
        f'<div class="hit139-note">{escape(ratio_note)}</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hit139-context{margin:7px 0 5px;padding:9px 10px;border:1px solid #3c4962;background:linear-gradient(145deg,#0d1624,#09131d);border-radius:12px}
.hit139-head{font-size:.44rem;letter-spacing:.08em;color:#9cc7ff;font-weight:950;text-transform:uppercase}
.hit139-main{font-size:.59rem;color:#eef6ff;line-height:1.5;margin-top:3px;font-weight:800}
.hit139-sub{font-size:.51rem;color:#aebfd3;line-height:1.48;margin-top:3px}.hit139-sub b{color:#dbeaff}
.hit139-risk{font-size:.49rem;color:#d7cf9b;line-height:1.45;margin-top:3px}.hit139-risk b{color:#f1e6ad}
.hit139-note{font-size:.43rem;color:#74879e;line-height:1.4;margin-top:4px}
.hit139-divider{height:1px;background:#26364b;margin:6px 0 4px}
</style>
"""

if "hit139-context" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v139(result, rank):
    """Inject Step 6 before probability while preserving verified V13.8 card HTML."""
    html = _BASE_PICK_HTML(result, rank)
    marker = '<div class="hit-pick-prob">'
    strip = _opportunity_strip(result)
    if marker in html:
        return html.replace(marker, strip + marker, 1)
    return html + strip


active._pick_html = _pick_html_v139


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🎯 Hit UI V13.9 • Step 6 plate-appearance + hit-opportunity context ACTIVE • "
        "display/context only • Hit Model V13 unchanged"
    )
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
