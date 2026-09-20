"""NFL Passing Yards V16 — cleanup step 4: matchup spotlight + why projection.

Presentation-only wrapper over certified V15. It adds a polished matchup strip with
team logos, QB-vs-defense pairing, and a compact "why this projection" summary
built entirely from already-computed certified Steps 1, 7, 8, 9 and 10 outputs.

No loader, projection, context, distribution, probability, market, grading, or
sportsbook-influence math changes. No new server-side data requests are made.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v15 as prior
import nfl_passing_yards_hub_v8 as step7_ui
import nfl_passing_yards_hub_v9 as step8_ui
import nfl_passing_yards_hub_v10 as step9_ui
import nfl_passing_yards_hub_v11 as step10_ui
from sports_universal_shell_v1 import render_universal_shell

MODEL_VERSION = "NFL PASSING YARDS V16 • CLEANUP STEP 4 • MATCHUP SPOTLIGHT"

_CLEANUP_STEP4_CSS = r"""
<style>
.kpy15-head,.kpy15-center{display:none!important}
.kpy16-head{border:1px solid #31546d;background:linear-gradient(135deg,#06111b,#0b1e2d);border-radius:15px;padding:12px 13px;margin:3px 0 8px;box-shadow:0 9px 26px rgba(0,0,0,.18)}
.kpy16-headrow{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.kpy16-title{font-size:1.2rem;font-weight:950;color:#f8fbff;letter-spacing:-.025em;line-height:1.05}.kpy16-title span{color:#7ff2c2}.kpy16-sub{font-size:.58rem;color:#8498aa;line-height:1.45;margin-top:4px;max-width:760px}.kpy16-status{border:1px solid #34795b;background:#09271d;color:#81edb7;border-radius:999px;padding:5px 8px;font-size:.48rem;font-weight:950;white-space:nowrap}
.kpy16-match{border:1px solid #28475d;background:#06111b;border-radius:14px;padding:10px;margin:0 0 8px}.kpy16-matchhead{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px}.kpy16-matchtitle{font-size:.78rem;font-weight:950;color:#eef7fb}.kpy16-matchsub{font-size:.45rem;color:#738a9d;margin-top:2px}.kpy16-tag{font-size:.42rem;font-weight:950;color:#bfe5ff;border:1px solid rgba(96,165,250,.58);background:linear-gradient(135deg,rgba(29,78,216,.36),rgba(2,132,199,.25));border-radius:999px;padding:6px 10px;white-space:nowrap;box-shadow:inset 0 0 0 1px rgba(125,211,252,.05),0 0 18px rgba(14,165,233,.08)}
.kpy16-versus{display:grid;grid-template-columns:1fr auto 1fr;gap:7px;align-items:stretch}.kpy16-side{border:1px solid #315269;background:#081521;border-radius:12px;padding:9px;min-width:0}.kpy16-sidehead{display:flex;align-items:center;gap:8px;margin-bottom:7px}.kpy16-logo{width:40px;height:40px;object-fit:contain;flex:0 0 auto;filter:drop-shadow(0 4px 8px rgba(0,0,0,.28))}.kpy16-team{font-size:.76rem;font-weight:950;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy16-site{font-size:.42rem;color:#6f8799;text-transform:uppercase;margin-top:2px}.kpy16-qb{font-size:.67rem;font-weight:900;color:#dce9f1;margin-bottom:2px}.kpy16-vsdef{font-size:.47rem;color:#7f96a8;line-height:1.45}.kpy16-at{align-self:center;color:#7ff2c2;font-size:.72rem;font-weight:950;border:1px solid #2d5e50;background:#082019;border-radius:999px;padding:5px 7px}
.kpy16-minis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:7px}.kpy16-mini{border:1px solid #1d394d;background:#05101a;border-radius:8px;padding:6px;min-width:0}.kpy16-mini b{display:block;color:#fff;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy16-mini span{display:block;color:#6c8395;font-size:.36rem;text-transform:uppercase;margin-top:2px}

/* Reference-style Why This Projection panel — presentation only. */
.kpy16-why{position:relative;overflow:hidden;border:1px solid rgba(55,130,246,.62);background:radial-gradient(circle at 50% -10%,rgba(20,89,190,.12),transparent 34%),linear-gradient(180deg,#071425 0%,#06101d 100%);border-radius:18px;padding:12px;margin:0 0 12px;box-shadow:inset 0 0 0 1px rgba(96,165,250,.035),0 14px 35px rgba(0,0,0,.18)}
.kpy16-why:after{content:"";position:absolute;left:18%;right:18%;bottom:-115px;height:170px;border-radius:50%;background:rgba(29,78,216,.055);filter:blur(30px);pointer-events:none}
.kpy16-whyhead{position:relative;z-index:1;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:10px;margin-bottom:11px;padding:2px 2px 1px}
.kpy16-brain{width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(139,92,246,.78);border-radius:50%;background:radial-gradient(circle at 35% 25%,rgba(244,114,182,.30),transparent 34%),linear-gradient(145deg,rgba(76,29,149,.72),rgba(23,19,68,.96));font-size:22px;box-shadow:0 0 0 4px rgba(99,102,241,.055),0 0 22px rgba(124,58,237,.18)}
.kpy16-whytitle{font-size:.92rem;font-weight:950;color:#fff;letter-spacing:-.01em}.kpy16-whysub{font-size:.46rem;color:#9cb0c5;margin-top:2px;line-height:1.45}
.kpy16-whygrid{position:relative;z-index:1;display:grid;grid-template-columns:1fr;gap:10px}
.kpy16-whycard{position:relative;overflow:hidden;border:1px solid rgba(37,99,235,.72);background:radial-gradient(circle at 78% 0%,rgba(14,165,233,.11),transparent 28%),linear-gradient(145deg,#07172b,#06111f);border-radius:17px;padding:11px;min-width:0;box-shadow:inset 0 0 0 1px rgba(96,165,250,.045),0 10px 25px rgba(0,0,0,.20)}
.kpy16-whytop{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:9px;margin-bottom:9px}
.kpy16-teamlogo-wrap{width:50px;height:50px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:1px solid rgba(56,189,248,.65);background:radial-gradient(circle at 30% 25%,rgba(59,130,246,.18),transparent 38%),#071426;box-shadow:0 0 18px rgba(14,165,233,.13)}
.kpy16-teamlogo{width:38px;height:38px;object-fit:contain}
.kpy16-whyident{min-width:0}.kpy16-whyname{font-size:.92rem;font-weight:950;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy16-whyteam{font-size:.43rem;color:#9cb0c5;text-transform:uppercase;letter-spacing:.16em;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpy16-conf{font-size:.42rem;font-weight:950;border-radius:999px;padding:6px 9px;border:1px solid rgba(96,165,250,.55);color:#bfdbfe;background:rgba(30,64,175,.14);white-space:nowrap;text-transform:uppercase;letter-spacing:.055em}.kpy16-conf.high{color:#86efac;border-color:rgba(74,222,128,.55);background:rgba(22,101,52,.16)}.kpy16-conf.medium{color:#bfdbfe;border-color:rgba(96,165,250,.58);background:rgba(30,64,175,.16)}.kpy16-conf.low{color:#fde68a;border-color:rgba(251,191,36,.55);background:rgba(146,64,14,.15)}
.kpy16-reasons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:4px}
.kpy16-reason{position:relative;overflow:hidden;min-height:66px;border-radius:11px;padding:9px 8px 8px;display:grid;grid-template-columns:28px minmax(0,1fr);grid-template-rows:auto auto;column-gap:7px;align-items:center}
.kpy16-reasonicon{grid-row:1/3;width:28px;height:28px;display:flex;align-items:center;justify-content:center;border-radius:9px;font-size:16px;background:rgba(255,255,255,.035)}
.kpy16-reason b{display:block;color:#fff;font-size:.72rem;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy16-reason span{display:block;font-size:.36rem;text-transform:uppercase;font-weight:950;letter-spacing:.065em}
.kpy16-r-volume{border:1px solid rgba(59,130,246,.58);background:linear-gradient(145deg,rgba(29,78,216,.25),rgba(8,23,44,.92))}.kpy16-r-volume span,.kpy16-r-volume .kpy16-reasonicon{color:#7dd3fc}
.kpy16-r-eff{border:1px solid rgba(45,212,191,.52);background:linear-gradient(145deg,rgba(13,148,136,.18),rgba(7,32,41,.94))}.kpy16-r-eff span,.kpy16-r-eff .kpy16-reasonicon{color:#99f6e4}
.kpy16-r-pressure{border:1px solid rgba(248,113,113,.58);background:linear-gradient(145deg,rgba(153,27,27,.22),rgba(42,17,25,.94))}.kpy16-r-pressure span,.kpy16-r-pressure .kpy16-reasonicon{color:#fca5a5}
.kpy16-r-personnel{border:1px solid rgba(250,204,21,.55);background:linear-gradient(145deg,rgba(161,98,7,.22),rgba(42,36,16,.94))}.kpy16-r-personnel span,.kpy16-r-personnel .kpy16-reasonicon{color:#fde68a}
.kpy16-r-weather{border:1px solid rgba(59,130,246,.58);background:linear-gradient(145deg,rgba(30,64,175,.23),rgba(11,30,58,.94))}.kpy16-r-weather span,.kpy16-r-weather .kpy16-reasonicon{color:#93c5fd}
.kpy16-r-sd{border:1px solid rgba(168,85,247,.58);background:linear-gradient(145deg,rgba(107,33,168,.24),rgba(35,19,56,.94))}.kpy16-r-sd span,.kpy16-r-sd .kpy16-reasonicon{color:#d8b4fe}
.kpy16-final{margin-top:9px;padding-top:9px;border-top:1px solid rgba(96,165,250,.34);display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:9px}
.kpy16-projicon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(99,102,241,.58);background:linear-gradient(145deg,rgba(67,56,202,.26),rgba(21,27,57,.92));color:#a5b4fc;font-size:18px}
.kpy16-proj{font-size:.72rem;color:#fff;font-weight:950}.kpy16-proj strong{color:#6ee7b7;font-size:1.05rem}.kpy16-market{font-size:.43rem;color:#9cb0c5;text-align:left;line-height:1.45;margin-top:2px}
.kpy16-grade{width:39px;height:39px;display:flex;align-items:center;justify-content:center;font-size:.72rem;font-weight:950;border-radius:50%;border:1px solid #415c70;color:#a8bbc9}.kpy16-grade.a,.kpy16-grade.b{color:#86efac;border-color:rgba(74,222,128,.75);background:rgba(22,101,52,.16);box-shadow:0 0 15px rgba(74,222,128,.12)}.kpy16-grade.c{color:#fde68a;border-color:rgba(251,191,36,.65);background:rgba(146,64,14,.15)}.kpy16-grade.pass{color:#bfdbfe;border-color:rgba(96,165,250,.6);background:rgba(30,64,175,.15)}
.kpy16-foot{position:relative;z-index:1;display:grid;grid-template-columns:34px minmax(0,1fr);gap:9px;align-items:center;font-size:.43rem;color:#9cb0c5;margin-top:10px;padding:10px;border:1px solid rgba(59,130,246,.42);border-radius:13px;background:linear-gradient(145deg,rgba(13,31,59,.82),rgba(8,20,39,.86));line-height:1.5}
.kpy16-foot:before{content:"ⓘ";display:flex;align-items:center;justify-content:center;width:32px;height:32px;border:2px solid #60a5fa;border-radius:50%;color:#60a5fa;font-size:17px;font-weight:950}

@media(max-width:700px){
  .kpy16-head{padding:11px 10px}.kpy16-title{font-size:1.08rem}.kpy16-sub{font-size:.55rem}.kpy16-status{font-size:.43rem;padding:4px 6px}.kpy16-match{padding:8px}.kpy16-versus{grid-template-columns:1fr}.kpy16-at{justify-self:center;padding:4px 7px}.kpy16-logo{width:36px;height:36px}.kpy16-minis{grid-template-columns:repeat(3,minmax(0,1fr))}
  .kpy16-why{padding:9px;border-radius:16px}.kpy16-whyhead{grid-template-columns:auto minmax(0,1fr);gap:8px}.kpy16-whyhead>.kpy16-tag{grid-column:1/-1;justify-self:stretch;text-align:center}.kpy16-brain{width:38px;height:38px;font-size:20px}.kpy16-whytitle{font-size:.84rem}.kpy16-whysub{font-size:.42rem}
  .kpy16-whycard{padding:9px}.kpy16-teamlogo-wrap{width:44px;height:44px}.kpy16-teamlogo{width:34px;height:34px}.kpy16-whyname{font-size:.82rem}.kpy16-whyteam{font-size:.38rem}.kpy16-conf{font-size:.37rem;padding:5px 7px}
  .kpy16-reasons{grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.kpy16-reason{min-height:59px;padding:7px 6px;grid-template-columns:24px minmax(0,1fr);column-gap:5px}.kpy16-reasonicon{width:24px;height:24px;font-size:14px}.kpy16-reason b{font-size:.62rem}.kpy16-reason span{font-size:.31rem}
  .kpy16-final{grid-template-columns:32px minmax(0,1fr) auto;gap:7px}.kpy16-projicon{width:32px;height:32px}.kpy16-proj{font-size:.64rem}.kpy16-proj strong{font-size:.92rem}.kpy16-market{font-size:.38rem}.kpy16-grade{width:34px;height:34px;font-size:.62rem}
}
@media(max-width:430px){
  .kpy16-whytop{grid-template-columns:auto minmax(0,1fr);align-items:start}.kpy16-whytop>.kpy16-conf{grid-column:1/-1;justify-self:start}.kpy16-reasons{grid-template-columns:repeat(3,minmax(0,1fr))}.kpy16-reason{grid-template-columns:1fr;grid-template-rows:auto auto auto;text-align:center}.kpy16-reasonicon{grid-row:auto;margin:0 auto 3px}.kpy16-reason b{font-size:.58rem}.kpy16-final{grid-template-columns:30px minmax(0,1fr) auto}.kpy16-foot{grid-template-columns:30px minmax(0,1fr);padding:8px}
}
</style>
"""

_HEADER = """
<section class="kpy16-head">
  <div class="kpy16-headrow">
    <div>
      <div class="kpy16-title">🏈 NFL <span>Passing Yards</span></div>
      <div class="kpy16-sub">Matchup first. See the quarterbacks, defenses, projection drivers, probability confidence, and market state before diving into the full certified Steps 1–10 evidence trail.</div>
    </div>
    <div class="kpy16-status">10 / 10 COMPLETE</div>
  </div>
</section>
"""


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    if not _finite(value):
        return "—"
    return f"{float(value):.{digits}f}{suffix}"


def _pct(value: Any) -> str:
    if not _finite(value):
        return "—"
    return f"{100.0 * float(value):.1f}%"


def _signed(value: Any, digits: int = 1, suffix: str = "") -> str:
    if not _finite(value):
        return "—"
    return f"{float(value):+.{digits}f}{suffix}"


def _confidence_class(value: Any) -> str:
    label = _safe(value, "CHECK").lower()
    return label if label in {"high", "medium", "low"} else ""


def _grade_class(value: Any) -> str:
    label = _safe(value, "CHECK").lower()
    return label if label in {"a", "b", "c", "pass"} else ""


def _logo_url(abbr: Any) -> str:
    token = _safe(abbr).lower()
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{token}.png" if token else ""


def _identity_side(ctx: dict, opponent: dict, baseline: dict, side_label: str) -> str:
    qb = ctx.get("qb1") or {}
    logo = _logo_url(ctx.get("abbr"))
    logo_html = f'<img class="kpy16-logo" src="{escape(logo)}" alt="{escape(_safe(ctx.get("team"), ctx.get("abbr")))} logo" loading="lazy">' if logo else ""
    defense_name = _safe(opponent.get("team"), opponent.get("abbr") or "Opponent")
    return (
        '<section class="kpy16-side">'
        '<div class="kpy16-sidehead">'
        f'{logo_html}<div><div class="kpy16-team">{escape(_safe(ctx.get("team"), ctx.get("abbr") or "Team"))}</div>'
        f'<div class="kpy16-site">{escape(side_label)}</div></div></div>'
        f'<div class="kpy16-qb">{escape(_safe(qb.get("name"), "Unresolved QB1"))}</div>'
        f'<div class="kpy16-vsdef">Quarterback vs <b>{escape(defense_name)}</b> pass defense • exact ESPN team/QB identity chain</div>'
        '<div class="kpy16-minis">'
        f'<div class="kpy16-mini"><b>{_fmt(baseline.get("expected_attempts"),1)}</b><span>Expected Att</span></div>'
        f'<div class="kpy16-mini"><b>{_fmt(baseline.get("expected_ypa"),2)}</b><span>Expected YPA</span></div>'
        f'<div class="kpy16-mini"><b>{_fmt(baseline.get("projection_yards"),1)}</b><span>Step 7 Base</span></div>'
        '</div></section>'
    )


def _matchup_html(identity_result: dict, baselines: list[dict]) -> str:
    if not identity_result:
        return ""
    away = identity_result.get("away") or {}
    home = identity_result.get("home") or {}
    if not away and not home:
        return ""
    away_base = baselines[0] if len(baselines) > 0 else {}
    home_base = baselines[1] if len(baselines) > 1 else {}
    ready = bool(identity_result.get("ready"))
    state = "IDENTITY VERIFIED" if ready else "IDENTITY CHECK"
    return (
        '<section class="kpy16-match">'
        '<div class="kpy16-matchhead">'
        '<div><div class="kpy16-matchtitle">🏟️ Matchup Spotlight</div>'
        '<div class="kpy16-matchsub">Quarterback vs opposing pass defense • logos are display-only ESPN team assets</div></div>'
        f'<div class="kpy16-tag">{escape(state)}</div></div>'
        '<div class="kpy16-versus">'
        f'{_identity_side(away, home, away_base, "AWAY")}'
        '<div class="kpy16-at">@</div>'
        f'{_identity_side(home, away, home_base, "HOME")}'
        '</div></section>'
    )


def _why_card(baseline: dict, context: dict, dist: dict, market: dict, team_ctx: dict | None = None) -> str:
    team_ctx = team_ctx or {}
    name = _safe(dist.get("qb_name") or context.get("qb_name") or baseline.get("qb_name"), "Unresolved QB1")
    confidence = _safe(dist.get("confidence") or context.get("confidence"), "CHECK").upper()
    conf_css = _confidence_class(confidence)
    projection_yards = dist.get("location_yards") if _finite(dist.get("location_yards")) else context.get("context_projection_yards")
    team_abbr = _safe(team_ctx.get("abbr"), "NFL").upper()
    team_name = _safe(team_ctx.get("team"), team_abbr)
    logo = _logo_url(team_abbr)
    logo_html = (
        f'<div class="kpy16-teamlogo-wrap"><img class="kpy16-teamlogo" src="{escape(logo, quote=True)}" alt="{escape(team_abbr, quote=True)} logo" loading="lazy"></div>'
        if logo else '<div class="kpy16-teamlogo-wrap"></div>'
    )
    if market.get("grade_ready"):
        lean = _safe(market.get("lean"), "PASS")
        grade = _safe(market.get("grade"), "PASS").upper()
        grade_css = _grade_class(grade)
        market_text = f"{lean} • line {_fmt(market.get('line'),1)} • O {_pct(market.get('model_over_probability'))} / U {_pct(market.get('model_under_probability'))}"
        grade_html = f'<span class="kpy16-grade {grade_css}">{escape(grade)}</span>'
    else:
        market_text = "MODEL READY • MARKET PENDING"
        grade_html = '<span class="kpy16-grade">CHECK</span>'
    return (
        '<section class="kpy16-whycard">'
        '<div class="kpy16-whytop">'
        f'{logo_html}'
        '<div class="kpy16-whyident">'
        f'<div class="kpy16-whyname">{escape(name)}</div>'
        f'<div class="kpy16-whyteam">QB • {escape(team_name)}</div></div>'
        f'<div class="kpy16-conf {conf_css}">{escape(confidence)} CONFIDENCE</div></div>'
        '<div class="kpy16-reasons">'
        f'<div class="kpy16-reason kpy16-r-volume"><span class="kpy16-reasonicon">▮▮▮</span><b>{_fmt(baseline.get("expected_attempts"),1)}</b><span>Volume</span></div>'
        f'<div class="kpy16-reason kpy16-r-eff"><span class="kpy16-reasonicon">◎</span><b>{_fmt(baseline.get("expected_ypa"),2)}</b><span>Efficiency</span></div>'
        f'<div class="kpy16-reason kpy16-r-pressure"><span class="kpy16-reasonicon">◈</span><b>{_signed(context.get("pressure_adjustment_yards"),1)}</b><span>Pressure Adj</span></div>'
        f'<div class="kpy16-reason kpy16-r-personnel"><span class="kpy16-reasonicon">●●●</span><b>{escape(_safe(context.get("personnel_context"),"CHECK"))}</b><span>Personnel</span></div>'
        f'<div class="kpy16-reason kpy16-r-weather"><span class="kpy16-reasonicon">☁</span><b>{escape(_safe(context.get("weather_context"),"CHECK"))}</b><span>Weather</span></div>'
        f'<div class="kpy16-reason kpy16-r-sd"><span class="kpy16-reasonicon">⌁</span><b>{_fmt(dist.get("sigma_yards"),1)}</b><span>Recent SD</span></div>'
        '</div>'
        '<div class="kpy16-final">'
        '<div class="kpy16-projicon">▣</div>'
        f'<div><div class="kpy16-proj">Projection: <strong>{_fmt(projection_yards,1)}</strong> yds</div><div class="kpy16-market">{escape(market_text)}</div></div>'
        f'{grade_html}'
        '</div></section>'
    )


def _why_html(
    baselines: list[dict],
    contexts: list[dict],
    distributions: list[dict],
    markets: list[dict],
    identity_result: dict | None = None,
) -> str:
    count = max(len(baselines), len(contexts), len(distributions), len(markets))
    if count <= 0:
        return ""
    identity_result = identity_result or {}
    teams = [identity_result.get("away") or {}, identity_result.get("home") or {}]
    cards = []
    for idx in range(count):
        baseline = baselines[idx] if idx < len(baselines) else {}
        context = contexts[idx] if idx < len(contexts) else {}
        dist = distributions[idx] if idx < len(distributions) else {}
        market = markets[idx] if idx < len(markets) else {}
        team_ctx = teams[idx] if idx < len(teams) else {}
        cards.append(_why_card(baseline, context, dist, market, team_ctx))
    return (
        '<section class="kpy16-why" data-reference-why-projection="true">'
        '<div class="kpy16-whyhead">'
        '<div class="kpy16-brain" aria-hidden="true">🧠</div>'
        '<div><div class="kpy16-whytitle">Why This Projection</div>'
        '<div class="kpy16-whysub">Fast read of the exact certified drivers already calculated below — no extra model pass.</div></div>'
        '<div class="kpy16-tag">RESULT → REASONS</div></div>'
        f'<div class="kpy16-whygrid">{"".join(cards)}</div>'
        '<div class="kpy16-foot">Only the certified Step 8 pressure-opportunity treatment can numerically move the Step 7 baseline here. Personnel/weather remain visible context with their existing certified 0.0-yard numerical treatment. Sportsbook projection influence remains exactly 0.0%.</div>'
        '</section>'
    )


def render_nfl_passing_yards_hub() -> None:
    render_universal_shell(sport="NFL", market="Passing Yards")
    st.markdown(_CLEANUP_STEP4_CSS, unsafe_allow_html=True)
    st.markdown(_HEADER, unsafe_allow_html=True)
    matchup_slot = st.empty()
    why_slot = st.empty()
    identity_result: dict = {}
    baselines: list[dict] = []
    contexts: list[dict] = []
    distributions: list[dict] = []
    markets: list[dict] = []
    original_identity = step7_ui.identity.resolve_matchup_identity
    original_baseline = step7_ui.projection.build_baseline_projection
    original_context = step8_ui.context.build_context_projection
    original_distribution = step9_ui.distribution.build_distribution
    original_market_card = step10_ui._market_card

    def capture_identity(*args, **kwargs):
        nonlocal identity_result
        row = original_identity(*args, **kwargs)
        identity_result = dict(row or {})
        return row

    def capture_baseline(*args, **kwargs):
        row = original_baseline(*args, **kwargs)
        baselines.append(dict(row or {}))
        return row

    def capture_context(*args, **kwargs):
        row = original_context(*args, **kwargs)
        contexts.append(dict(row or {}))
        return row

    def capture_distribution(*args, **kwargs):
        row = original_distribution(*args, **kwargs)
        distributions.append(dict(row or {}))
        return row

    def capture_market_card(row: dict):
        markets.append(dict(row or {}))
        return original_market_card(row)

    step7_ui.identity.resolve_matchup_identity = capture_identity
    step7_ui.projection.build_baseline_projection = capture_baseline
    step8_ui.context.build_context_projection = capture_context
    step9_ui.distribution.build_distribution = capture_distribution
    step10_ui._market_card = capture_market_card
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        step7_ui.identity.resolve_matchup_identity = original_identity
        step7_ui.projection.build_baseline_projection = original_baseline
        step8_ui.context.build_context_projection = original_context
        step9_ui.distribution.build_distribution = original_distribution
        step10_ui._market_card = original_market_card

    matchup = _matchup_html(identity_result, baselines)
    reasons = _why_html(baselines, contexts, distributions, markets, identity_result)
    if matchup:
        matchup_slot.markdown(matchup, unsafe_allow_html=True)
    if reasons:
        why_slot.markdown(reasons, unsafe_allow_html=True)


__all__ = ["MODEL_VERSION", "_CLEANUP_STEP4_CSS", "_logo_url", "_matchup_html", "_why_html", "render_nfl_passing_yards_hub"]
