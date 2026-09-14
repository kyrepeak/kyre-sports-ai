"""NFL Passing Yards V29 — visual parity Step 2 QB hero cards + page shell.

Additive presentation-only wrapper over frozen certified V28. V29 begins the
six-step Passing Yards visual-parity build so the page shares the same polished
player-first design language as certified Receiving Yards and Rushing Yards.

This layer changes presentation only:
- reskins the legacy Passing shell into the green/black card family;
- replaces the plain Step 1 QB identity cards with compact hero cards;
- reuses exact verified ESPN team/QB identity for logo/headshot display;
- adds exact away/home matchup text only after both sides verify;
- preserves V28 -> V20 data/model/market behavior unchanged.

Projection, distribution, probability, fair odds, no-vig, EV, grading, market
semantics and transport remain frozen. Sportsbook projection influence remains
exactly 0.0%. Stake sizing remains OFF.
"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v2 as step1_ui
import nfl_passing_yards_hub_v8 as step7_ui
import nfl_passing_yards_hub_v21 as team_visual_ui
import nfl_passing_yards_hub_v22 as player_visual_ui
import nfl_passing_yards_hub_v28 as prior

MODEL_VERSION = "NFL PASSING YARDS V29 • VISUAL PARITY STEP 2 • QB HERO CARDS"
FROZEN_PRIOR = "nfl_passing_yards_hub_v28"
VISUAL_BUILD_STEP = 2
VISUAL_BUILD_TOTAL = 6
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_QB_CARD_V2 = step1_ui._qb_card

_VISUAL_PARITY_CSS = r'''
<style>
/* Passing visual-parity shell: deliberately presentation-only. */
.kpass29-build{position:relative;overflow:hidden;border:1px solid #315940;border-radius:17px;background:linear-gradient(145deg,#0b1712 0%,#0a1411 68%,#0d1a14 100%);padding:11px 12px;margin:4px 0 12px}
.kpass29-build:after{content:"";position:absolute;right:-38px;bottom:-70px;width:170px;height:170px;border:1px solid rgba(139,226,172,.06);border-radius:50%;box-shadow:0 0 0 22px rgba(139,226,172,.018)}
.kpass29-buildtop{position:relative;z-index:1;display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.kpass29-buildtitle{color:#f5faf7;font-size:.96rem;font-weight:950;line-height:1.15}.kpass29-buildsub{color:#789083;font-size:.54rem;line-height:1.45;margin-top:3px}
.kpass29-buildchips{position:relative;z-index:1;display:flex;flex-wrap:wrap;gap:5px;justify-content:flex-end}.kpass29-buildchip{display:inline-flex;align-items:center;border:1px solid #3c6a4d;background:#0f2418;color:#8be2ac;border-radius:999px;padding:4px 7px;font-size:.44rem;font-weight:950;letter-spacing:.04em;white-space:nowrap}.kpass29-buildchip.blue{border-color:#435e76;background:#111e29;color:#a9c5df}.kpass29-buildchip.gold{border-color:#6d613a;background:#241f12;color:#dcc06d}
.kpass29-track{position:relative;z-index:1;height:5px;border-radius:999px;background:#13241a;overflow:hidden;margin-top:9px}.kpass29-fill{width:33.333%;height:100%;border-radius:999px;background:linear-gradient(90deg,#5fb979,#9be3ae)}

/* Bring legacy Passing shell into the certified Receiving/Rushing visual family. */
.kpy-head{border-color:#315940!important;background:linear-gradient(145deg,#0b1712,#0a1411)!important;border-radius:17px!important}.kpy-title span{color:#8be2ac!important}.kpy-sub{color:#789083!important}.kpy-chip{border-color:#3c6a4d!important;background:#0f2418!important;color:#8be2ac!important;border-radius:999px!important}.kpy-strip{border-color:#263d31!important;background:#0b1611!important;border-radius:14px!important}.kpy-stat{border-color:#1e3528!important;background:#09140f!important}.kpy-stat b{color:#edf6f0!important}.kpy-stat span{color:#617568!important}.kpy-step{border-color:#263d31!important;background:#0b1611!important;border-radius:14px!important}.kpy-step-title{color:#eef7f1!important}.kpy-step-sub{color:#71877a!important}

.kpass29-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:8px 0 12px}
.kpass29-card{position:relative;overflow:hidden;border:1px solid #2b4b39;border-radius:17px;background:linear-gradient(145deg,#0b1712 0%,#0a1411 70%,#0d1a14 100%);padding:10px 11px;min-width:0}
.kpass29-card:after{content:"";position:absolute;right:-28px;bottom:-55px;width:130px;height:130px;border:1px solid rgba(139,226,172,.055);border-radius:50%;box-shadow:0 0 0 18px rgba(139,226,172,.018)}
.kpass29-top{position:relative;z-index:1;display:flex;align-items:center;gap:9px;min-width:0}
.kpass29-head{width:54px;height:54px;flex:0 0 54px;border:1px solid #355b45;border-radius:50%;overflow:hidden;background:#09140f;display:flex;align-items:flex-end;justify-content:center}.kpass29-head img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
.kpass29-ident{min-width:0;flex:1}.kpass29-name{color:#f6faf7;font-size:.84rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpass29-meta{color:#7d9285;font-size:.51rem;line-height:1.45;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpass29-logo{width:36px;height:36px;flex:0 0 36px;border:1px solid #284334;border-radius:10px;background:#09150f;padding:4px;box-sizing:border-box;object-fit:contain}
.kpass29-badges{display:flex;flex-wrap:wrap;gap:5px;margin-top:5px}.kpass29-badge{display:inline-flex;align-items:center;border:1px solid #3c6a4d;background:#0f2418;color:#8be2ac;border-radius:999px;padding:3px 6px;font-size:.43rem;font-weight:950;letter-spacing:.04em}.kpass29-badge.blue{border-color:#435e76;background:#111e29;color:#a9c5df}.kpass29-badge.gold{border-color:#6d613a;background:#241f12;color:#dcc06d}
.kpass29-main{position:relative;z-index:1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:9px}.kpass29-metric{border:1px solid #1e3528;border-radius:10px;background:#09140f;padding:7px 8px;min-width:0}.kpass29-metric b{display:block;color:#f0f7f2;font-size:.70rem;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpass29-metric span{display:block;color:#62786a;font-size:.42rem;text-transform:uppercase;font-weight:900;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpass29-foot{position:relative;z-index:1;border-top:1px solid #1a2d22;margin-top:7px;padding-top:6px;color:#6f8477;font-size:.46rem;line-height:1.45}.kpass29-foot strong{color:#91cda4}
@media(max-width:760px){.kpass29-buildtop{flex-direction:column}.kpass29-buildchips{justify-content:flex-start}.kpass29-grid{grid-template-columns:1fr}.kpass29-card{padding:9px 10px}.kpass29-head{width:48px;height:48px;flex-basis:48px}.kpass29-main{grid-template-columns:repeat(2,minmax(0,1fr))}.kpass29-main>.kpass29-metric:first-child{grid-column:1/-1}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _exact_visual(ctx: dict[str, Any]) -> dict[str, Any]:
    qb = (ctx or {}).get("qb1") or {}
    team_id = _safe((ctx or {}).get("team_id"), "")
    athlete_id = _safe(qb.get("athlete_id"), "")
    abbr = _safe((ctx or {}).get("abbr"), "").upper()
    ready = bool((ctx or {}).get("identity_verified") and team_id.isdigit() and athlete_id.isdigit())
    return {
        "ready": ready,
        "team_id": team_id if ready else "",
        "team_abbr": abbr if ready else "",
        "team_name": _safe((ctx or {}).get("team"), abbr) if ready else "",
        "athlete_id": athlete_id if ready else "",
        "player_name": _safe(qb.get("name"), "Quarterback") if ready else "",
    }


def _matchup_map(identity_result: dict[str, Any]) -> dict[str, dict[str, str]]:
    away = (identity_result or {}).get("away") or {}
    home = (identity_result or {}).get("home") or {}
    away_v = _exact_visual(away)
    home_v = _exact_visual(home)
    if not (away_v.get("ready") and home_v.get("ready")):
        return {}
    return {
        str(away_v["team_id"]): {"opponent_abbr": str(home_v["team_abbr"]), "venue_token": "@"},
        str(home_v["team_id"]): {"opponent_abbr": str(away_v["team_abbr"]), "venue_token": "vs"},
    }


def _qb_hero_card(ctx: dict[str, Any], preseason: bool, matchup: dict[str, str] | None = None) -> str:
    qb = (ctx or {}).get("qb1") or {}
    visual = _exact_visual(ctx)
    player_name = _safe(qb.get("name"), "Unresolved QB1")
    team_abbr = _safe((ctx or {}).get("abbr"), "NFL").upper()
    team_name = _safe((ctx or {}).get("team"), team_abbr)
    team_id = _safe((ctx or {}).get("team_id"), "—")
    athlete_id = _safe(qb.get("athlete_id"), "—")
    injury = _safe(qb.get("injury_status"), "No listed injury")
    source = _safe((ctx or {}).get("depth_source"), "No verified depth source")
    status, note = step1_ui._status_label(ctx, preseason)
    healthy = bool((ctx or {}).get("identity_verified") and not (ctx or {}).get("availability_alert"))
    status_class = "blue" if healthy else "gold"

    matchup = matchup or {}
    opponent = _safe(matchup.get("opponent_abbr"), "")
    venue = _safe(matchup.get("venue_token"), "")
    matchup_text = f"{team_abbr} {venue} {opponent}" if opponent and venue in {"@", "vs"} else team_abbr

    headshot = player_visual_ui._player_headshot_url(visual)
    logo = team_visual_ui._team_logo_url(visual)
    head_html = (
        f'<div class="kpass29-head"><img src="{escape(headshot, quote=True)}" alt="{escape(player_name, quote=True)} headshot" loading="lazy" decoding="async" onerror="this.style.display=\'none\'"></div>'
        if headshot else '<div class="kpass29-head"></div>'
    )
    logo_html = (
        f'<img class="kpass29-logo" src="{escape(logo, quote=True)}" alt="{escape(team_abbr, quote=True)} logo" loading="lazy" decoding="async" onerror="this.style.display=\'none\'">'
        if logo else ""
    )
    exact_badge = "EXACT-ID QB1" if visual.get("ready") else "QB ID CHECK"

    return (
        '<article class="kpass29-card">'
        '<div class="kpass29-top">'
        f'{head_html}'
        '<div class="kpass29-ident">'
        f'<div class="kpass29-name">{escape(player_name)}</div>'
        f'<div class="kpass29-meta">QB • {escape(matchup_text)} • {escape(team_name)}</div>'
        '<div class="kpass29-badges">'
        f'<span class="kpass29-badge">{escape(exact_badge)}</span>'
        f'<span class="kpass29-badge {status_class}">{escape(status)}</span>'
        '</div></div>'
        f'{logo_html}</div>'
        '<div class="kpass29-main">'
        f'<div class="kpass29-metric"><b>{escape(athlete_id)}</b><span>ESPN Athlete ID</span></div>'
        f'<div class="kpass29-metric"><b>{escape(team_id)}</b><span>ESPN Team ID</span></div>'
        f'<div class="kpass29-metric"><b>{escape(injury)}</b><span>Availability</span></div>'
        '</div>'
        '<div class="kpass29-foot">'
        f'{escape(source)} • {escape(note)} • exact ESPN identity only • '
        '<strong>sportsbook projection influence 0.0%</strong>'
        '</div></article>'
    )


def _visual_build_banner() -> str:
    return (
        '<section class="kpass29-build">'
        '<div class="kpass29-buildtop"><div>'
        '<div class="kpass29-buildtitle">🎨 Passing Yards • Visual Parity Build</div>'
        '<div class="kpass29-buildsub">Same player-first design family as certified Receiving Yards + Rushing Yards • underlying Passing model remains frozen at 10/10.</div>'
        '</div><div class="kpass29-buildchips">'
        '<span class="kpass29-buildchip">VISUAL STEP 2 / 6</span>'
        '<span class="kpass29-buildchip blue">V28 ENGINE FROZEN</span>'
        '<span class="kpass29-buildchip gold">SPORTSBOOK 0%</span>'
        '</div></div><div class="kpass29-track"><div class="kpass29-fill"></div></div>'
        '</section>'
    )


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_VISUAL_PARITY_CSS, unsafe_allow_html=True)
    st.markdown(_visual_build_banner(), unsafe_allow_html=True)

    matchups: dict[str, dict[str, str]] = {}
    original_identity = step7_ui.identity.resolve_matchup_identity
    original_qb_card = step1_ui._qb_card

    def capture_identity(*args, **kwargs):
        result = original_identity(*args, **kwargs)
        matchups.clear()
        matchups.update(_matchup_map(result or {}))
        return result

    def qb_card_with_visual(ctx: dict[str, Any], preseason: bool) -> str:
        team_id = _safe((ctx or {}).get("team_id"), "")
        return _qb_hero_card(ctx, preseason, matchups.get(team_id, {}))

    step7_ui.identity.resolve_matchup_identity = capture_identity
    step1_ui._qb_card = qb_card_with_visual
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        step7_ui.identity.resolve_matchup_identity = original_identity
        step1_ui._qb_card = original_qb_card


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V29 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VISUAL_BUILD_STEP",
    "VISUAL_BUILD_TOTAL",
    "_exact_visual",
    "_matchup_map",
    "_qb_hero_card",
    "_visual_build_banner",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
