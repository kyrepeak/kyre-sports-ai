"""MLB 1+ Hit UI V13.18 — Step 3 hitter true-talent + contact quality.

Additive evidence-only wrapper over permanently frozen Hits Step 2 / UI V13.17.

Step 3 adds a compact player-skill profile to each Top-5 card using frozen Hit
Model source helpers for:
- season AVG / hits per PA / K%,
- Baseball Savant xBA,
- L10 AVG + hit-game rate,
- Avg EV / Hard-Hit% / Barrel%,
- a reliability-shrunk neutral hit-skill blend,
- existing frozen Statcast contact grade.

No game-level probability, Monte Carlo, candidate-pool, Top-5 ranking,
calibration/history or market behavior is changed.
"""
from __future__ import annotations

from html import escape
import math
import re
from typing import Any, Mapping

import streamlit as st

import mlb_hit_hub_v1317 as prior
import mlb_hit_hitter_profile_v1 as profile

active, core, visual = prior.active, prior.core, prior.visual
UI_VERSION = "V13.18"
_BASE_PICK_HTML = prior._pick_html_v1317


def _f(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _pct(value: Any, digits: int = 1) -> str:
    x = _f(value)
    return "N/A" if x is None else f"{x * 100:.{digits}f}%"


def _avg(value: Any) -> str:
    x = _f(value)
    return "N/A" if x is None else f"{x:.3f}"


def _one(value: Any) -> str:
    x = _f(value)
    return "N/A" if x is None else f"{x:.1f}"


def _skill_class(label: Any) -> str:
    text = str(label or "").upper()
    if "ELITE" in text or "STRONG" in text:
        return "good"
    if "WEAK" in text:
        return "bad"
    if "DATA LIMITED" in text:
        return "limited"
    return "neutral"


def _profile_html(context: Mapping[str, Any] | None) -> str:
    c = dict(context or {})
    if not c:
        c = {
            "skill_label": "DATA LIMITED",
            "data_label": "LOW PROFILE DATA",
            "data_score": 0,
        }

    weights = c.get("skill_weights") or {}
    skill = _f(c.get("neutral_hit_skill"))
    skill_text = _avg(skill)
    sample = int(c.get("pa") or 0)
    recent_games = int(c.get("recent_games") or 0)

    return (
        '<div class="hit1318-profile">'
        '<div class="hit1318-head">'
        '<div>'
        '<span class="hit1318-kicker">STEP 3 • HITTER TRUE-TALENT + CONTACT QUALITY</span>'
        f'<b>{escape(str(c.get("skill_label") or "DATA LIMITED"))}</b>'
        '</div>'
        f'<span class="hit1318-data">{escape(str(c.get("data_label") or "LOW PROFILE DATA"))} • {int(c.get("data_score") or 0)}/100</span>'
        '</div>'
        '<div class="hit1318-grid">'
        f'<div><b>{escape(_avg(c.get("season_avg")))}</b><span>Season AVG</span></div>'
        f'<div><b>{escape(_avg(c.get("xba")))}</b><span>xBA</span></div>'
        f'<div><b>{escape(_avg(c.get("recent_avg")))}</b><span>L10 AVG</span></div>'
        f'<div><b>{escape(_pct(c.get("recent_hit_game_rate")))}</b><span>L10 hit-game</span></div>'
        f'<div><b>{escape(_pct(c.get("k_pct")))}</b><span>K%</span></div>'
        f'<div><b>{escape(_one(c.get("avg_ev")))}</b><span>Avg EV</span></div>'
        f'<div><b>{escape(_pct(c.get("hard_hit_pct")))}</b><span>Hard-Hit%</span></div>'
        f'<div><b>{escape(_pct(c.get("barrel_pct")))}</b><span>Barrel%</span></div>'
        '</div>'
        '<div class="hit1318-read">'
        f'<span class="hit1318-skill {_skill_class(c.get("skill_label"))}">Neutral hit skill • {escape(skill_text)}</span>'
        f'<span>Contact • {escape(str(c.get("contact_grade") or "DATA LIMITED"))}</span>'
        f'<span>Season sample • {sample} PA</span>'
        f'<span>Recent sample • {recent_games} G</span>'
        '</div>'
        '<div class="hit1318-note">'
        'Player-only evidence layer. Neutral blend is season-dominant with reliability-shrunk xBA and recent AVG. '
        f'Current normalized weights: season {_pct(weights.get("season"), 0)} • xBA {_pct(weights.get("xba"), 0)} • recent {_pct(weights.get("recent"), 0)}. '
        'Starter, bullpen, park/weather, lineup opportunity and sportsbook price are excluded here. '
        '<b>Probability / ranking impact: NONE.</b>'
        '</div>'
        '</div>'
    )


def _inject_before_deep(card: str, panel: str) -> str:
    text = str(card or "")
    if not panel or "hit1318-profile" in text:
        return text
    marker = '<details class="hit1317-deep">'
    idx = text.find(marker)
    if idx >= 0:
        return text[:idx] + panel + text[idx:]
    close = text.rfind("</div>")
    if close >= 0:
        return text[:close] + panel + text[close:]
    return text + panel


def _pick_html_v1318(result, rank):
    """Render frozen Step 2 first, then add player-only Step 3 evidence."""
    frozen_html = str(_BASE_PICK_HTML(result, rank) or "")
    r = result or {}
    player_id = r.get("player_id")
    fallback_avg = r.get("season_avg")

    try:
        context = profile.build_hitter_profile(int(player_id), _f(fallback_avg))
    except Exception:
        context = {
            "skill_label": "DATA LIMITED",
            "data_label": "LOW PROFILE DATA",
            "data_score": 0,
            "probability_impact": False,
            "ranking_impact": False,
        }

    return _inject_before_deep(frozen_html, _profile_html(context))


active._pick_html = _pick_html_v1318

_CSS = r"""
<style>
.hit1318-profile{margin-top:9px;border:1px solid rgba(93,202,255,.22);border-radius:11px;background:linear-gradient(145deg,#0a1d2b,#08151f);padding:8px 9px}
.hit1318-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap}.hit1318-head>div{min-width:0}.hit1318-kicker{display:block;color:#65d8ff;font-size:.40rem;font-weight:950;letter-spacing:.07em;text-transform:uppercase}.hit1318-head b{display:block;color:#f1f8fc;font-size:.61rem;margin-top:2px}.hit1318-data{display:inline-flex;border-radius:999px;padding:4px 6px;border:1px solid #315367;background:#0b1d28;color:#a5c7d9;font-size:.39rem;font-weight:900}
.hit1318-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.hit1318-grid>div{border:1px solid #1d384a;background:#081722;border-radius:8px;padding:5px;text-align:center;min-width:0}.hit1318-grid b{display:block;color:#f0f6fa;font-size:.53rem}.hit1318-grid span{display:block;color:#6f8796;font-size:.34rem;text-transform:uppercase;margin-top:2px}
.hit1318-read{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}.hit1318-read span{display:inline-flex;border-radius:999px;padding:4px 6px;border:1px solid #294353;background:#0b1923;color:#a8b9c5;font-size:.37rem;font-weight:850}.hit1318-read .hit1318-skill.good{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hit1318-read .hit1318-skill.bad{border-color:#7b3c39;background:#361615;color:#ff9f9a}.hit1318-read .hit1318-skill.limited{border-color:#465564;background:#16202a;color:#a8b4c0}
.hit1318-note{margin-top:6px;color:#728996;font-size:.37rem;line-height:1.45}.hit1318-note b{color:#9edcff}
@media(max-width:700px){.hit1318-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hit1318-profile{padding:8px}.hit1318-note{font-size:.36rem}}
</style>
"""
if "hit1318-profile" not in core.HIT_CSS:
    core.HIT_CSS += _CSS


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🧬 Hit UI V13.18 • Step 3 hitter true-talent + contact profile ACTIVE • "
        "player-only evidence • Hit Model V13 probability/ranking unchanged"
    )
    return prior.render_hit_hub(games_df, section_header, status_info, team_logo, h)


__all__ = [
    "UI_VERSION",
    "_BASE_PICK_HTML",
    "_inject_before_deep",
    "_pick_html_v1318",
    "_profile_html",
    "render_hit_hub",
]
