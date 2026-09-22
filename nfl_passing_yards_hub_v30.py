"""NFL Passing Yards V30 — visual parity Step 3 summary + QB profile.

Additive presentation-only wrapper over certified V29. V30 upgrades the frozen
Passing Yards slate summary and Step 2 quarterback profile into the same compact,
player-first green/black design family used by certified Receiving Yards and
Rushing Yards.

No profile statistic, projection, probability, fair odds, EV, grade, market
transport, recommendation or stake behavior is changed. All displayed profile
values are read from the frozen V3 profile object. V29/V28 remain frozen and
sportsbook projection influence stays exactly 0.0%.
"""
from __future__ import annotations

from html import escape
from typing import Any

import nfl_passing_yards_hub_v3 as profile_ui
import nfl_passing_yards_hub_v29 as prior

MODEL_VERSION = "NFL PASSING YARDS V30 • VISUAL PARITY STEP 3 • SUMMARY + QB PROFILE"
FROZEN_PRIOR = "nfl_passing_yards_hub_v29"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
VISUAL_BUILD_STEP = 3
VISUAL_BUILD_TOTAL = 6
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_PROFILE_CARD_V3 = profile_ui._profile_card
_ORIGINAL_VISUAL_BANNER_V29 = prior._visual_build_banner
_ORIGINAL_VISUAL_CSS_V29 = prior._VISUAL_PARITY_CSS

_STEP3_VISUAL_CSS = r'''
<style>
/* Step 3 slate summary: same compact metric-tile family as Receiving/Rushing. */
.kpy-strip{display:grid!important;grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:6px!important;border:0!important;background:transparent!important;padding:0!important;margin:8px 0 11px!important}
.kpy-stat{position:relative;overflow:hidden;border:1px solid #2a4a38!important;border-radius:11px!important;background:linear-gradient(145deg,#0a1711 0%,#09130f 100%)!important;padding:8px 9px!important;min-width:0!important}
.kpy-stat:after{content:"";position:absolute;right:-22px;bottom:-30px;width:70px;height:70px;border:1px solid rgba(139,226,172,.045);border-radius:50%}
.kpy-stat b{position:relative;z-index:1;color:#eef7f1!important;font-size:.74rem!important;line-height:1.1!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy-stat span{position:relative;z-index:1;color:#667b6e!important;font-size:.42rem!important;font-weight:900!important;letter-spacing:.035em!important;text-transform:uppercase!important;margin-top:3px!important}

.kpass30-profile{position:relative;overflow:hidden;border:1px solid #2c4d3a;border-radius:16px;background:linear-gradient(145deg,#0b1712 0%,#09140f 72%,#0d1a14 100%);padding:10px 11px;min-width:0}
.kpass30-profile:after{content:"";position:absolute;right:-38px;top:-46px;width:145px;height:145px;border:1px solid rgba(139,226,172,.045);border-radius:50%;box-shadow:0 0 0 18px rgba(139,226,172,.014)}
.kpass30-head{position:relative;z-index:1;display:flex;align-items:flex-start;justify-content:space-between;gap:8px;padding-bottom:8px;border-bottom:1px solid #1b3024}.kpass30-name{color:#f6faf7;font-size:.84rem;font-weight:950;line-height:1.15}.kpass30-sub{color:#73877a;font-size:.47rem;line-height:1.45;margin-top:3px}.kpass30-state{border:1px solid #3b6a4c;background:#0f2418;color:#8be2ac;border-radius:999px;padding:4px 7px;font-size:.42rem;font-weight:950;letter-spacing:.04em;white-space:nowrap}.kpass30-state.check{border-color:#6d613a;background:#241f12;color:#dcc06d}
.kpass30-hero{position:relative;z-index:1;display:grid;grid-template-columns:1.25fr repeat(2,minmax(0,1fr));gap:6px;margin-top:8px}.kpass30-herostat{border:1px solid #21402e;border-radius:11px;background:#08130e;padding:8px 9px;min-width:0}.kpass30-herostat:first-child{border-color:#356247;background:linear-gradient(145deg,#0e2317,#09160f)}.kpass30-herostat b{display:block;color:#f5faf6;font-size:1.0rem;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpass30-herostat:first-child b{color:#a6e8b8;font-size:1.14rem}.kpass30-herostat span{display:block;color:#667c6e;font-size:.42rem;font-weight:900;text-transform:uppercase;margin-top:3px}
.kpass30-season{position:relative;z-index:1;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px;margin-top:6px}.kpass30-mini{border:1px solid #1d3527;border-radius:9px;background:#09140f;padding:6px 7px;min-width:0}.kpass30-mini b{display:block;color:#edf6f0;font-size:.69rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpass30-mini span{display:block;color:#607366;font-size:.39rem;text-transform:uppercase;font-weight:900;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpass30-formtitle{position:relative;z-index:1;color:#8be2ac;font-size:.43rem;font-weight:950;letter-spacing:.045em;text-transform:uppercase;margin-top:8px}.kpass30-form{position:relative;z-index:1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:4px}.kpass30-formcell{border:1px solid #1b3024;border-radius:9px;background:#08120d;padding:6px 7px;min-width:0}.kpass30-formcell b{display:block;color:#eaf4ed;font-size:.65rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpass30-formcell span{display:block;color:#5f7266;font-size:.38rem;text-transform:uppercase;font-weight:900;margin-top:2px}
.kpass30-foot{position:relative;z-index:1;border-top:1px solid #1a2e22;margin-top:7px;padding-top:6px;color:#6c8174;font-size:.43rem;line-height:1.45}.kpass30-foot strong{color:#91cda4}
@media(max-width:820px){.kpy-strip{grid-template-columns:repeat(2,minmax(0,1fr))!important}.kpy-stat:last-child{grid-column:1/-1}.kpass30-hero{grid-template-columns:repeat(2,minmax(0,1fr))}.kpass30-herostat:first-child{grid-column:1/-1}.kpass30-season{grid-template-columns:repeat(2,minmax(0,1fr))}.kpass30-season>.kpass30-mini:last-child{grid-column:1/-1}.kpass30-form{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _profile_card_v30(team_ctx: dict[str, Any], qb_profile: dict[str, Any]) -> str:
    """Restyle frozen V3 profile values without recomputing any statistic."""
    qb = (team_ctx or {}).get("qb1") or {}
    season = (qb_profile or {}).get("season") or {}
    name = _safe(qb.get("name"), "Unresolved QB1")
    team = _safe((team_ctx or {}).get("team"), (team_ctx or {}).get("abbr") or "NFL")
    athlete_id = _safe((qb_profile or {}).get("athlete_id"), qb.get("athlete_id") or "—")
    ready = bool((qb_profile or {}).get("ready"))
    state = "PROFILE GREEN" if ready else "PROFILE CHECK"
    state_class = "" if ready else " check"

    yards_game = profile_ui._fmt(season.get("yards_per_game"), 1)
    attempts_game = profile_ui._fmt(season.get("attempts_per_game"), 1)
    ypa = profile_ui._fmt(season.get("yards_per_attempt"), 2)
    completion = profile_ui._fmt(season.get("completion_pct"), 1, "%")
    games = profile_ui._count(season.get("games"))
    total_yards = profile_ui._count(season.get("passing_yards"))
    pass_tds = profile_ui._count(season.get("passing_tds"))
    interceptions = profile_ui._count(season.get("interceptions"))

    recent3 = profile_ui._fmt((qb_profile or {}).get("recent3_yards"), 1)
    recent5 = profile_ui._fmt((qb_profile or {}).get("recent5_yards"), 1)
    home_yards = profile_ui._fmt((qb_profile or {}).get("home_yards"), 1)
    away_yards = profile_ui._fmt((qb_profile or {}).get("away_yards"), 1)
    season_http = _safe((qb_profile or {}).get("season_http"), "—")
    gamelog_http = _safe((qb_profile or {}).get("gamelog_http"), "—")

    return (
        '<section class="kpass30-profile">'
        '<div class="kpass30-head">'
        f'<div><div class="kpass30-name">{escape(name)} • Passing Profile</div>'
        f'<div class="kpass30-sub">{escape(team)} • ESPN athlete {escape(athlete_id)} • frozen descriptive profile</div></div>'
        f'<span class="kpass30-state{state_class}">{escape(state)}</span>'
        '</div>'
        '<div class="kpass30-hero">'
        f'<div class="kpass30-herostat"><b>{escape(yards_game)}</b><span>Pass Yards / Game</span></div>'
        f'<div class="kpass30-herostat"><b>{escape(attempts_game)}</b><span>Attempts / Game</span></div>'
        f'<div class="kpass30-herostat"><b>{escape(ypa)}</b><span>Yards / Attempt</span></div>'
        '</div>'
        '<div class="kpass30-season">'
        f'<div class="kpass30-mini"><b>{escape(completion)}</b><span>Completion</span></div>'
        f'<div class="kpass30-mini"><b>{escape(games)}</b><span>Games</span></div>'
        f'<div class="kpass30-mini"><b>{escape(total_yards)}</b><span>Pass Yards</span></div>'
        f'<div class="kpass30-mini"><b>{escape(pass_tds)}</b><span>Pass TD</span></div>'
        f'<div class="kpass30-mini"><b>{escape(interceptions)}</b><span>INT</span></div>'
        '</div>'
        '<div class="kpass30-formtitle">Recent Form + Location Splits</div>'
        '<div class="kpass30-form">'
        f'<div class="kpass30-formcell"><b>{escape(recent3)}</b><span>Recent 3 Yds/G</span></div>'
        f'<div class="kpass30-formcell"><b>{escape(recent5)}</b><span>Recent 5 Yds/G</span></div>'
        f'<div class="kpass30-formcell"><b>{escape(home_yards)}</b><span>Home Yds/G</span></div>'
        f'<div class="kpass30-formcell"><b>{escape(away_yards)}</b><span>Away Yds/G</span></div>'
        '</div>'
        '<div class="kpass30-foot">'
        f'Season stats HTTP: {escape(season_http)} • game log HTTP: {escape(gamelog_http)} • '
        '<strong>display-only • profile math unchanged • sportsbook projection influence 0.0%</strong>'
        '</div></section>'
    )


def _visual_build_banner_v30() -> str:
    return (
        '<section class="kpass29-build">'
        '<div class="kpass29-buildtop"><div>'
        '<div class="kpass29-buildtitle">🎨 Passing Yards • Visual Parity Build</div>'
        '<div class="kpass29-buildsub">Fun summary metrics + QB passing profiles now share the certified Receiving/Rushing card language • underlying Passing model remains frozen.</div>'
        '</div><div class="kpass29-buildchips">'
        '<span class="kpass29-buildchip">VISUAL STEP 3 / 6</span>'
        '<span class="kpass29-buildchip blue">V29 + V28 FROZEN</span>'
        '<span class="kpass29-buildchip gold">SPORTSBOOK 0%</span>'
        '</div></div><div class="kpass29-track"><div class="kpass29-fill" style="width:50%"></div></div>'
        '</section>'
    )


def render_nfl_passing_yards_hub() -> None:
    original_profile = profile_ui._profile_card
    original_banner = prior._visual_build_banner
    original_css = prior._VISUAL_PARITY_CSS
    profile_ui._profile_card = _profile_card_v30
    prior._visual_build_banner = _visual_build_banner_v30
    prior._VISUAL_PARITY_CSS = original_css + _STEP3_VISUAL_CSS
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        profile_ui._profile_card = original_profile
        prior._visual_build_banner = original_banner
        prior._VISUAL_PARITY_CSS = original_css


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V30 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VISUAL_BUILD_STEP",
    "VISUAL_BUILD_TOTAL",
    "_profile_card_v30",
    "_visual_build_banner_v30",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
