"""CFB Over/Under Clean Page V17.

This is the first Over/Under page that does NOT render through the legacy
Step-1/Step-2 monkey-patch chain.

Direct page architecture
------------------------
Schedule V5 runtime snapshot
-> Runtime Team Data V1
-> Runtime Slate V14
-> NEW Step 1 current matchup renderer
-> NEW Step 2 current rankings/records renderer
-> direct Step 3-12 model result panels

The frozen model engines remain unchanged and are invoked only through the
direct runtime slate. The legacy Step-1/Step-2 presentation modules are not
imported here and cannot render this page.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_over_under_final_v1 as final_model
import cfb_over_under_logo_resolver_v2 as logo_resolver
import cfb_over_under_runtime_team_data_v1 as runtime_team_data
import cfb_over_under_slate_v14_runtime as runtime_slate
import cfb_over_under_step3_readable_v2 as readable_step3
import cfb_schedule_v5_runtime_snapshot as schedule

MODEL_VERSION = "CFB O/U CLEAN PAGE V17.3 • STEP 3 FAVORABLE / TOUGH VERDICTS"
MARKET = "Over/Under"
_ET = ZoneInfo("America/New_York")

_CSS = r"""
<style>
.c17-shell{border:1px solid rgba(67,195,255,.22);border-radius:18px;
background:linear-gradient(145deg,#07131d,#081a24 55%,#091711);overflow:hidden;margin:10px 0}
.c17-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:10px 12px;
border-bottom:1px solid rgba(67,195,255,.11)}
.c17-head b{color:#82ddff;font-size:.53rem;font-weight:950;letter-spacing:.08em}
.c17-pill{border:1px solid #2e7356;border-radius:999px;background:#09281d;color:#8fe8b9;
padding:4px 7px;font-size:.36rem;font-weight:950;white-space:nowrap}
.c17-teams{display:grid;grid-template-columns:minmax(0,1fr) 48px minmax(0,1fr);gap:8px;align-items:center;padding:12px}
.c17-team{display:grid;grid-template-columns:62px minmax(0,1fr);gap:9px;align-items:center;
border:1px solid rgba(150,190,215,.12);border-radius:13px;background:#08151e;padding:9px}
.c17-team.home{text-align:right;grid-template-columns:minmax(0,1fr) 62px}
.c17-team.home .c17-logo{grid-column:2}.c17-team.home .c17-copy{grid-column:1;grid-row:1}
.c17-logo{width:62px;height:62px;border:1px solid rgba(255,255,255,.09);border-radius:12px;
display:flex;align-items:center;justify-content:center;background:#0c1b24;overflow:hidden}
.c17-logo img{width:52px;height:52px;object-fit:contain}.c17-mono{font-weight:950;color:#d9eef8}
.c17-rank{font-size:.40rem;color:#79dfff;font-weight:950;text-transform:uppercase}
.c17-name{font-size:1.02rem;color:#f4fbff;font-weight:950;margin-top:2px}
.c17-meta{font-size:.45rem;color:#91a7b3;font-weight:800;margin-top:5px;line-height:1.5}
.c17-at{text-align:center;color:#7c96a4;font-size:.40rem;font-weight:900}.c17-at b{display:block;color:#e4f0f5;font-size:1rem}
.c17-context{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border-top:1px solid rgba(67,195,255,.10)}
.c17-context div{padding:8px 9px;border-right:1px solid rgba(67,195,255,.08)}
.c17-context div:last-child{border-right:0}.c17-context small{display:block;color:#7090a0;font-size:.31rem;font-weight:950;text-transform:uppercase}
.c17-context strong{display:block;color:#dcebf2;font-size:.48rem;margin-top:3px}
.c17-grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}
.c17-card{border:1px solid rgba(224,183,77,.17);border-radius:13px;background:#0d171a;padding:9px}
.c17-card h4{margin:0;color:#eef6f4;font-size:.74rem}.c17-sub{color:#81959a;font-size:.36rem;margin-top:2px}
.c17-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:8px}
.c17-metric{border:1px solid rgba(120,160,180,.10);border-radius:8px;background:#081319;padding:6px}
.c17-metric b{display:block;color:#bde8fb;font-size:.51rem}.c17-metric span{display:block;color:#687f89;font-size:.26rem;text-transform:uppercase;margin-top:2px}
.c17-ranks{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}
.c17-rankbox{border:1px solid rgba(80,210,150,.10);border-radius:8px;background:#071812;padding:6px}
.c17-rankbox b{display:block;color:#9be8c1;font-size:.48rem}.c17-rankbox span{display:block;color:#607c6e;font-size:.25rem;text-transform:uppercase}
.c17-step{border:1px solid rgba(126,175,205,.17);border-radius:13px;background:#08141c;margin-top:8px;overflow:hidden;box-shadow:inset 3px 0 0 var(--step-accent,#7eaecb)}
.c17-step-h{display:flex;justify-content:space-between;gap:8px;padding:8px 10px;border-bottom:1px solid rgba(126,175,205,.09);background:linear-gradient(90deg,var(--step-wash,rgba(126,175,205,.06)),transparent 72%)}
.c17-step-h b{color:var(--step-accent,#d8ecf5);font-size:.48rem;letter-spacing:.06em}.c17-step-h span{font-size:.34rem;font-weight:900}.c17-step-h span.ready{color:#81dcae}.c17-step-h span.limited{color:#f1c76f}.c17-step-h span.gated{color:#ff9d7a}.c17-step-h span.check{color:#9fb3bd}
.c17-step.step-3{--step-accent:#ff746b;--step-wash:rgba(255,116,107,.10);border-color:rgba(255,116,107,.28);background:linear-gradient(145deg,#160d10,#0b151b 72%)}
.c17-s3-wrap{padding:9px}
.c17-s3-intro{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:0 1px 8px;color:#a6bac4;font-size:.36rem;line-height:1.45}
.c17-s3-intro b{color:#ffd2cf;font-size:.40rem}.c17-s3-zero{color:#8fe8b9;font-weight:900;white-space:nowrap}
.c17-s3-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.c17-s3-battle{border:1px solid rgba(255,116,107,.20);border-radius:12px;background:#08141a;overflow:hidden}
.c17-s3-battle-h{padding:8px 9px;background:linear-gradient(90deg,rgba(255,116,107,.10),rgba(8,20,26,.30));border-bottom:1px solid rgba(255,116,107,.12)}
.c17-s3-battle-h strong{display:block;color:#f7fbfd;font-size:.62rem;line-height:1.25}.c17-s3-battle-h span{display:block;color:#94aab4;font-size:.31rem;margin-top:3px}
.c17-s3-table{padding:6px}
.c17-s3-row{display:grid;grid-template-columns:1.12fr .88fr .88fr .95fr;gap:4px;align-items:center;padding:6px 4px;border-bottom:1px solid rgba(130,160,175,.07)}
.c17-s3-row:last-child{border-bottom:0}.c17-s3-row.head{padding-top:2px;color:#6f8793;font-size:.25rem;font-weight:950;text-transform:uppercase}
.c17-s3-label{color:#cbdce4;font-size:.34rem;font-weight:900}.c17-s3-val{color:#f0f7fa;font-size:.42rem;font-weight:950}
.c17-s3-sub{display:block;color:#6d8590;font-size:.24rem;font-weight:700;margin-top:1px}.c17-s3-diff{font-size:.31rem;font-weight:950}
.c17-s3-diff.pos{color:#ffb79e}.c17-s3-diff.neg{color:#87d5ff}.c17-s3-diff.neutral{color:#a7b5bc}
.c17-s3-summary{padding:7px 9px;border-top:1px solid rgba(255,116,107,.10);color:#9cb0ba;font-size:.32rem;line-height:1.4}
.c17-s3-verdict{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;padding:7px 8px;border-top:1px solid rgba(255,116,107,.10);background:#071118}
.c17-s3-verdict-box{border-radius:8px;padding:7px 8px;border:1px solid rgba(255,255,255,.08)}
.c17-s3-verdict-box small{display:block;font-size:.25rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin-bottom:3px}
.c17-s3-verdict-box strong{display:block;font-size:.46rem;line-height:1.2}
.c17-s3-verdict-box.fav{background:rgba(65,205,133,.08);border-color:rgba(65,205,133,.24)}.c17-s3-verdict-box.fav small{color:#78dca7}.c17-s3-verdict-box.fav strong{color:#dff9ea}
.c17-s3-verdict-box.tough{background:rgba(255,105,105,.08);border-color:rgba(255,105,105,.24)}.c17-s3-verdict-box.tough small{color:#ff9292}.c17-s3-verdict-box.tough strong{color:#ffe4e4}
.c17-s3-verdict-meta{grid-column:1/-1;color:#7f98a3;font-size:.28rem;line-height:1.35;padding:1px 2px}

.c17-s3-source{padding:8px 10px;color:#768d98;font-size:.31rem;line-height:1.45;border-top:1px solid rgba(255,116,107,.10)}

.c17-step.step-4{--step-accent:#c7d2dc;--step-wash:rgba(199,210,220,.09);border-color:rgba(199,210,220,.22);background:linear-gradient(145deg,#10161d,#09151c 72%)}
.c17-step.step-5{--step-accent:#ff9a52;--step-wash:rgba(255,154,82,.10);border-color:rgba(255,154,82,.27);background:linear-gradient(145deg,#17110b,#0b151a 72%)}
.c17-step.step-6{--step-accent:#ff5f70;--step-wash:rgba(255,95,112,.10);border-color:rgba(255,95,112,.27);background:linear-gradient(145deg,#180c11,#0b151a 72%)}
.c17-step.step-7{--step-accent:#b984ff;--step-wash:rgba(185,132,255,.10);border-color:rgba(185,132,255,.27);background:linear-gradient(145deg,#130d1b,#0a151b 72%)}
.c17-step.step-8{--step-accent:#f6a04d;--step-wash:rgba(246,160,77,.10);border-color:rgba(246,160,77,.27);background:linear-gradient(145deg,#17110b,#0b151a 72%)}
.c17-step.step-9{--step-accent:#62baff;--step-wash:rgba(98,186,255,.10);border-color:rgba(98,186,255,.28);background:linear-gradient(145deg,#091422,#0a151b 72%)}
.c17-step.step-10{--step-accent:#d07cff;--step-wash:rgba(208,124,255,.10);border-color:rgba(208,124,255,.27);background:linear-gradient(145deg,#150d1b,#0a151b 72%)}
.c17-step.step-11{--step-accent:#64df9b;--step-wash:rgba(100,223,155,.10);border-color:rgba(100,223,155,.27);background:linear-gradient(145deg,#0a1812,#0a151b 72%)}
.c17-step.step-12{--step-accent:#f2c94c;--step-wash:rgba(242,201,76,.10);border-color:rgba(242,201,76,.30);background:linear-gradient(145deg,#17150a,#0a151b 72%)}
.c17-step-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:8px}
.c17-note{padding:8px 10px;color:#6f8793;font-size:.34rem;line-height:1.45;border-top:1px solid rgba(126,175,205,.08)}
.c17-final{border:1px solid rgba(84,220,151,.28);border-radius:15px;background:#071a12;margin-top:10px;padding:11px}
.c17-final b{color:#8ce8b8;font-size:.50rem}.c17-final strong{display:block;color:#effff6;font-size:1.5rem;margin-top:4px}
.c17-final span{color:#85a391;font-size:.42rem}
@media(max-width:760px){
 .c17-teams{grid-template-columns:1fr}.c17-at{min-height:24px}.c17-team,.c17-team.home{grid-template-columns:54px minmax(0,1fr);text-align:left}
 .c17-team.home .c17-logo{grid-column:1}.c17-team.home .c17-copy{grid-column:2;grid-row:1}
 .c17-context{grid-template-columns:repeat(2,minmax(0,1fr))}.c17-context div:last-child{grid-column:1/-1}
 .c17-grid2,.c17-s3-grid{grid-template-columns:1fr}.c17-metrics,.c17-ranks,.c17-step-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
 .c17-s3-row{grid-template-columns:1.05fr .86fr .86fr .92fr}.c17-s3-label{font-size:.31rem}.c17-s3-val{font-size:.38rem}\n .c17-s3-verdict{grid-template-columns:1fr}
}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _record(value: Any) -> str:
    if isinstance(value, Mapping):
        wins = int(value.get("wins") or 0)
        losses = int(value.get("losses") or 0)
        ties = int(value.get("ties") or 0)
        return f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    return _clean(value) or "—"


def _poll(profile: Mapping[str, Any], key: str) -> str:
    if _clean(profile.get("division_context")).upper() == "FCS":
        return "N/A"
    polls = profile.get("polls") or {}
    row = polls.get(key) or {}
    rank = row.get("rank")
    if rank is None:
        field = {
            "ap": "ap_rank",
            "coaches": "coaches_poll_rank",
            "cfp": "cfp_rank",
        }.get(key, "")
        rank = profile.get(field) if field else None
    try:
        return f"#{int(rank)}" if rank is not None else ("NOT YET" if key == "cfp" else "NR")
    except Exception:
        return "NR"


def _monogram(name: str) -> str:
    tokens = [x for x in _clean(name).replace("&", " ").split() if x]
    return "".join(x[0].upper() for x in tokens[:2]) or "CFB"


def _logo_html(name: str, visual: Mapping[str, Any]) -> str:
    url = _clean(visual.get("logo"))
    if url:
        return f'<div class="c17-logo"><img src="{escape(url)}" alt="{escape(name)} logo"></div>'
    return f'<div class="c17-logo"><span class="c17-mono">{escape(_monogram(name))}</span></div>'


def _rank_label(profile: Mapping[str, Any]) -> str:
    if _clean(profile.get("division_context")).upper() == "FCS":
        return "FCS"
    rank = profile.get("ap_rank")
    try:
        return f"#{int(rank)} AP" if rank is not None else "UNRANKED"
    except Exception:
        return "UNRANKED"


def _team_step1(side: str, profile: Mapping[str, Any], visual: Mapping[str, Any]) -> str:
    name = _clean(profile.get("team")) or side.title()
    conference = _clean(profile.get("conference")) or "Conference unavailable"
    overall = _clean(profile.get("record_text")) or "—"
    conf_record = _clean(profile.get("conference_record_text")) or "—"
    coach = _clean(profile.get("head_coach")) or "Coach unavailable"
    home_cls = " home" if side == "home" else ""
    copy = f'''
<div class="c17-copy">
 <div class="c17-rank">{escape(_rank_label(profile))}</div>
 <div class="c17-name">{escape(name)}</div>
 <div class="c17-meta">{escape(conference)} • {escape(overall)} overall • {escape(conf_record)} conf<br>{escape(coach)}</div>
</div>'''
    logo = _logo_html(name, visual)
    return f'<div class="c17-team{home_cls}">{copy}{logo}</div>' if side == "home" else f'<div class="c17-team{home_cls}">{logo}{copy}</div>'


def _step1(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    try:
        visuals = logo_resolver.resolve_visuals(game)
    except Exception:
        visuals = {"away": {}, "home": {}}
    site = "Neutral site" if bool(game.get("neutral_site")) else "Home field"
    return f'''
<div class="c17-shell">
 <div class="c17-head"><b>🧩 STEP 1 • CURRENT MATCHUP IDENTITY</b><span class="c17-pill">NEW RENDERER • RUNTIME DATA</span></div>
 <div class="c17-teams">
  {_team_step1("away", away, visuals.get("away") or {})}
  <div class="c17-at"><b>@</b>MATCHUP</div>
  {_team_step1("home", home, visuals.get("home") or {})}
 </div>
 <div class="c17-context">
  <div><small>Kickoff</small><strong>{escape(_clean(game.get("kickoff_et")) or "TBD")}</strong></div>
  <div><small>Stadium</small><strong>{escape(_clean(game.get("venue")) or "Venue unavailable")}</strong></div>
  <div><small>TV</small><strong>{escape(_clean(game.get("broadcast")) or "Broadcast unavailable")}</strong></div>
  <div><small>Status</small><strong>{escape(_clean(game.get("status")) or "Status unavailable")}</strong></div>
  <div><small>Site</small><strong>{escape(site)}</strong></div>
 </div>
</div>'''


_METRIC_ORDER = (
    "total_offense",
    "scoring_offense",
    "pass_offense",
    "rush_offense",
    "total_defense",
    "scoring_defense",
    "pass_defense",
    "rush_defense",
)


def _official_rank_boxes(profile: Mapping[str, Any]) -> str:
    stats = profile.get("official_stats") or {}
    boxes: list[str] = []
    for key in _METRIC_ORDER:
        row = stats.get(key) or {}
        if not isinstance(row, Mapping):
            continue
        rank = row.get("rank")
        label = _clean(row.get("label") or key.replace("_", " "))
        value = row.get("value")
        rank_text = f"#{int(rank)}" if rank is not None else "—"
        boxes.append(
            f'<div class="c17-rankbox"><b>{escape(rank_text)}</b><span>{escape(label)}'
            + (f' • {escape(_num(value,1))}' if value is not None else "")
            + '</span></div>'
        )
    return "".join(boxes) or '<div class="c17-rankbox"><b>—</b><span>official category ranks unavailable</span></div>'


def _team_step2(profile: Mapping[str, Any]) -> str:
    name = escape(_clean(profile.get("team")) or "Team")
    conf = escape(_clean(profile.get("conference")) or "Conference unavailable")
    division = escape(_clean(profile.get("division_context")) or "CFB")
    metrics = [
        ("Overall", _clean(profile.get("record_text")) or "—"),
        ("Conference", _clean(profile.get("conference_record_text")) or "—"),
        ("Home", _record(profile.get("home_record") or {})),
        ("Road", _record(profile.get("away_record") or {})),
        ("Recent", _clean(profile.get("recent_form")) or "—"),
        ("AP", _poll(profile, "ap")),
        ("Coaches", _poll(profile, "coaches")),
        ("CFP", _poll(profile, "cfp")),
    ]
    metric_html = "".join(
        f'<div class="c17-metric"><b>{escape(str(value))}</b><span>{escape(label)}</span></div>'
        for label, value in metrics
    )
    return f'''
<div class="c17-card">
 <h4>{name}</h4><div class="c17-sub">{conf} • {division} • Head coach: {escape(_clean(profile.get("head_coach")) or "unavailable")}</div>
 <div class="c17-metrics">{metric_html}</div>
 <div class="c17-ranks">{_official_rank_boxes(profile)}</div>
</div>'''


def _step2(away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    return f'''
<div class="c17-shell">
 <div class="c17-head"><b>🏆 STEP 2 • CURRENT RANKINGS + RECORDS</b><span class="c17-pill">NO LEGACY STEP-2 ENGINE</span></div>
 <div class="c17-grid2">{_team_step2(away)}{_team_step2(home)}</div>
 <div class="c17-note">Polls and records come from the runtime current-data profile. NCAA category ranks remain official-stat evidence only and have 0% direct selection weight.</div>
</div>'''


def _s3_value(value: Any, key: str) -> str:
    try:
        number = float(value)
    except Exception:
        return "—"
    digits = 2 if key == "yards_per_play" else 1
    return f"{number:.{digits}f}"


def _s3_difference(value: Any, key: str) -> tuple[str, str]:
    try:
        number = float(value)
    except Exception:
        return "—", "neutral"
    digits = 2 if key == "yards_per_play" else 1
    text = f"{number:+.{digits}f}"
    if abs(number) < (0.01 if digits == 2 else 0.05):
        return text, "neutral"
    return text, "pos" if number > 0 else "neg"


def _s3_battle_html(battle: Mapping[str, Any]) -> str:
    offense = _clean(battle.get("offense_team")) or "Offense"
    defense = _clean(battle.get("defense_team")) or "Defense"
    offense_sample = _clean(battle.get("offense_sample")) or "SAMPLE CHECK"
    defense_sample = _clean(battle.get("defense_sample")) or "SAMPLE CHECK"

    rows_html: list[str] = []
    for row in battle.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        key = _clean(row.get("key"))
        label = _clean(row.get("label")) or key.replace("_", " ").title()
        off = _s3_value(row.get("offense_value"), key)
        allowed = _s3_value(row.get("defense_value"), key)
        diff, diff_cls = _s3_difference(row.get("difference"), key)
        off_suffix = _clean(row.get("offense_suffix"))
        def_suffix = _clean(row.get("defense_suffix"))
        rows_html.append(
            f'<div class="c17-s3-row">'
            f'<div class="c17-s3-label">{escape(label)}</div>'
            f'<div class="c17-s3-val">{escape(off)}<span class="c17-s3-sub">{escape(off_suffix)}</span></div>'
            f'<div class="c17-s3-val">{escape(allowed)}<span class="c17-s3-sub">{escape(def_suffix)}</span></div>'
            f'<div class="c17-s3-diff {escape(diff_cls)}">{escape(diff)}<span class="c17-s3-sub">production − allowance</span></div>'
            f'</div>'
        )

    summary = _clean(battle.get("summary")) or "Current production and allowance shown without inventing an edge grade."
    favorable_for = _clean(battle.get("favorable_for")) or "No clear side"
    tough_for = _clean(battle.get("tough_for")) or "No clear side"
    verdict_reason = _clean(battle.get("verdict_reason")) or "Current sample is mixed."
    verdict_basis = _clean(battle.get("verdict_basis")) or "CURRENT SAMPLE ONLY"
    verdict = _clean(battle.get("verdict")) or "CURRENT-SAMPLE MIXED"
    return f'''
<div class="c17-s3-battle">
 <div class="c17-s3-battle-h">
  <strong>{escape(offense)} OFFENSE → {escape(defense)} DEFENSE</strong>
  <span>{escape(offense_sample)} offense • {escape(defense_sample)} defense</span>
 </div>
 <div class="c17-s3-table">
  <div class="c17-s3-row head"><div>Category</div><div>{escape(offense)} offense</div><div>{escape(defense)} allows</div><div>Difference</div></div>
  {''.join(rows_html) or '<div class="c17-s3-row"><div class="c17-s3-label">Current stats unavailable</div></div>'}
 </div>
 <div class="c17-s3-verdict">
  <div class="c17-s3-verdict-box fav"><small>✓ Favorable for</small><strong>{escape(favorable_for)}</strong></div>
  <div class="c17-s3-verdict-box tough"><small>⚠ Tough for</small><strong>{escape(tough_for)}</strong></div>
  <div class="c17-s3-verdict-meta">{escape(verdict)} • {escape(verdict_basis)} • {escape(verdict_reason)}</div>
 </div>
 <div class="c17-s3-summary">{escape(summary)}.</div>
</div>'''


def _step3_readable(
    readable: Mapping[str, Any],
    certified_engine: Mapping[str, Any],
) -> str:
    display_ready = bool(readable.get("display_ready"))
    status = "DATA READY" if display_ready else "DATA LIMITED"
    status_class = "ready" if display_ready else "limited"
    sample = _clean(readable.get("sample_state")) or "CURRENT SAMPLE CHECK"
    certified_status = _engine_ready(certified_engine)
    certified_plain = {
        "READY": "certified matchup model ready",
        "LIMITED": "certified matchup model limited",
        "GATED": "certified matchup model gated",
        "CHECK": "certified matchup model check",
    }.get(certified_status, "certified matchup model check")

    if not display_ready:
        reason = _clean(readable.get("reason")) or "Current readable Step 3 evidence is incomplete."
        return f'''
<div class="c17-step step-3">
 <div class="c17-step-h"><b>STEP 3 • OFFENSE VS DEFENSE</b><span class="{status_class}">{status}</span></div>
 <div class="c17-note">{escape(reason)} No old developer-number renderer is used as a fallback.</div>
</div>'''

    away_battle = readable.get("away_offense_vs_home_defense") or {}
    home_battle = readable.get("home_offense_vs_away_defense") or {}
    sources = " • ".join(
        _clean(item) for item in (readable.get("sources") or []) if _clean(item)
    )
    return f'''
<div class="c17-step step-3">
 <div class="c17-step-h"><b>STEP 3 • OFFENSE VS DEFENSE</b><span class="{status_class}">{status}</span></div>
 <div class="c17-s3-wrap">
  <div class="c17-s3-intro">
   <div><b>{escape(sample)}</b><br>Current-season production is compared directly with the opponent's current-season allowance. Difference is descriptive, not a made-up power rating.</div>
   <div class="c17-s3-zero">NEW READABLE LAYER • 0% NEW PROJECTION WEIGHT</div>
  </div>
  <div class="c17-s3-grid">{_s3_battle_html(away_battle)}{_s3_battle_html(home_battle)}</div>
 </div>
 <div class="c17-s3-source">Sources: {escape(sources or "current verified team and exact-game data")} • {escape(certified_plain)} underneath • sportsbook/price/EV input: 0%.</div>
</div>'''


def _engine_ready(engine: Mapping[str, Any]) -> str:
    """Return a truthful presentation status without changing model math.

    Engines that expose model_ready must only show READY when model_ready=True.
    A generic ready=True on those engines means the audit object itself exists,
    not that its adjustment is allowed to influence the projection.
    """
    if "model_ready" in engine:
        if engine.get("model_ready") is True:
            return "READY"
        try:
            coverage = float(engine.get("coverage") or 0.0)
        except Exception:
            coverage = 0.0
        return "LIMITED" if coverage > 0.0 else "GATED"

    if engine.get("ready") is True:
        return "READY"

    try:
        coverage = float(engine.get("coverage") or 0.0)
    except Exception:
        coverage = 0.0
    if coverage > 0.0:
        return "LIMITED"
    return "GATED" if _clean(engine.get("reason")) else "CHECK"


def _interesting(engine: Mapping[str, Any], limit: int = 8) -> list[tuple[str, str]]:
    preferred = (
        "coverage","adjustment","sigma","expected","possessions","pace","rate",
        "strength","stress","meetings","games","sample","weight","advantage",
        "probability","projected","total","offense","defense",
    )
    rows: list[tuple[str, str]] = []
    for key, value in engine.items():
        if key in {"attempts","sample","rows","diagnostics","source_url","source"}:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (str, int, float)) and any(token in key.lower() for token in preferred):
            if isinstance(value, float):
                display = _num(value, 3)
            else:
                display = _clean(value)
            if display:
                rows.append((key.replace("_", " "), display))
        if len(rows) >= limit:
            break
    return rows


def _model_step(step: int, title: str, engine: Mapping[str, Any]) -> str:
    status = _engine_ready(engine)
    metrics = _interesting(engine)
    metric_html = "".join(
        f'<div class="c17-metric"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
        for label, value in metrics
    ) or '<div class="c17-metric"><b>—</b><span>no numeric summary</span></div>'
    reason = _clean(engine.get("reason")) or "Current verified inputs processed through the frozen certified engine."
    status_class = status.lower()
    influence_note = ""
    if status == "GATED":
        influence_note = " • 0% new model influence; prior certified projection remains active."
    elif status == "LIMITED":
        influence_note = " • Partial evidence is visible, but the engine has not cleared its full model-ready gate."
    return f'''
<div class="c17-step step-{int(step)}">
 <div class="c17-step-h"><b>STEP {step} • {escape(title)}</b><span class="{escape(status_class)}">{escape(status)}</span></div>
 <div class="c17-step-grid">{metric_html}</div>
 <div class="c17-note">{escape(reason + influence_note)}</div>
</div>'''


def _cert_step(result: Mapping[str, Any]) -> str:
    cert = result.get("certification") or {}
    status = _clean(cert.get("status")) or "CHECK"
    failed = int(cert.get("checks_failed") or 0)
    return f'''
<div class="c17-step step-12">
 <div class="c17-step-h"><b>STEP 12 • FINAL CERTIFICATION</b><span class="ready">{escape(status)}</span></div>
 <div class="c17-step-grid">
  <div class="c17-metric"><b>{failed}</b><span>integrity failures</span></div>
  <div class="c17-metric"><b>{escape(_clean(result.get("version")) or "runtime slate")}</b><span>model stack</span></div>
  <div class="c17-metric"><b>0%</b><span>sportsbook input</span></div>
  <div class="c17-metric"><b>0%</b><span>Monte Carlo added</span></div>
 </div>
</div>'''


def _final(result: Mapping[str, Any]) -> str:
    raw = result.get("raw") or {}
    final = result.get("final") or {}
    selection = _clean(final.get("selection") or final.get("pick") or raw.get("model_lean")) or "PASS"
    probability = final.get("selection_probability")
    if probability is None:
        probability = raw.get("under_probability") if selection.upper() == "UNDER" else raw.get("over_probability")
    return f'''
<div class="c17-final">
 <b>FINAL OVER/UNDER OUTPUT</b>
 <strong>{escape(selection)}</strong>
 <span>Projected total {_num(raw.get("projected_total"),1)} • analysis line {_num(result.get("analysis_line"),1)} • selection probability {_pct(probability)} • structural sigma {_num(raw.get("structural_total_sigma"),2)}</span>
</div>'''


def _line_board(games: list[Mapping[str, Any]], selected_identity: str, selected_line: float) -> list[dict[str, Any]]:
    rows = []
    for game in games:
        identity = _clean(game.get("identity_key") or game.get("game_id"))
        rows.append({
            "Use": identity == selected_identity,
            "Matchup": f"{game.get('away_team')} @ {game.get('home_team')}",
            "Kickoff ET": game.get("kickoff_et"),
            "Analysis Line": float(selected_line),
            "Identity": identity,
        })
    return rows


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.caption("🟢 CFB O/U • CLEAN PAGE V17 ACTIVE • LEGACY STEP 1/2 RENDERERS RETIRED")
    st.markdown(_CSS, unsafe_allow_html=True)

    selected = st.date_input(
        "📅 CFB Over/Under slate date",
        value=datetime.now(_ET).date(),
        key="cfb_ou_v17_date",
    )
    day = selected.isoformat()

    games, schedule_diag = schedule.load_with_diagnostics(day)
    if not games:
        st.warning("No verified College Football games were returned for this date.")
        return

    st.caption(
        f"Schedule: {len(games)} games • "
        f"{int(schedule_diag.get('espn_matches') or 0)} enriched matches • "
        f"{int(schedule_diag.get('venue_missing') or 0)} venue missing • "
        f"{int(schedule_diag.get('broadcast_missing') or 0)} broadcast missing"
    )

    index = st.selectbox(
        "🏟️ Over/Under matchup",
        options=list(range(len(games))),
        format_func=lambda i: (
            f"{games[int(i)].get('away_team')} @ {games[int(i)].get('home_team')} "
            f"• {games[int(i)].get('kickoff_et') or 'TBD'}"
        ),
        key=f"cfb_ou_v17_matchup_{day}",
    )
    selected_game = dict(games[int(index)])
    identity = _clean(selected_game.get("identity_key") or selected_game.get("game_id") or index)

    line = st.number_input(
        "🎯 Selected-game analysis total line — threshold only (0% projection weight)",
        min_value=20.0,
        max_value=100.0,
        value=50.5,
        step=0.5,
        key=f"cfb_ou_v17_line_{day}_{identity}",
    )

    try:
        result = runtime_slate.analyze_game(selected_game, day, float(line))
    except Exception as exc:
        st.error(f"Current runtime analysis failed visibly: {type(exc).__name__}: {exc}")
        return

    game = dict(result.get("game") or selected_game)
    away = dict(result.get("away") or {})
    home = dict(result.get("home") or {})
    diag = result.get("team_diag") or {}

    runtime_status = _clean(diag.get("runtime_status")) or "CHECK"
    if runtime_status == "GREEN":
        st.success("🟢 CURRENT TEAM DATA PATH GREEN — no record/venue/broadcast contradictions detected.")
    else:
        st.warning(
            "🟡 Current team data path is not fully green: "
            + " • ".join(str(x) for x in (diag.get("runtime_issues") or [])[:4])
        )

    st.markdown(_step1(game, away, home), unsafe_allow_html=True)
    st.markdown(_step2(away, home), unsafe_allow_html=True)

    try:
        readable_matchup = readable_step3.build_matchup_step3(game, away, home)
    except Exception as exc:
        readable_matchup = {
            "ready": True,
            "display_ready": False,
            "reason": f"Readable Step 3 data failed visibly: {type(exc).__name__}: {exc}",
        }
    st.markdown(
        _step3_readable(
            readable_matchup,
            result.get("matchup_engine") or {},
        ),
        unsafe_allow_html=True,
    )
    st.markdown(_model_step(4, "PACE / EXPECTED POSSESSIONS", result.get("pace_engine") or {}), unsafe_allow_html=True)
    st.markdown(_model_step(5, "EXPLOSIVE PLAY PROFILE", result.get("explosive_engine") or {}), unsafe_allow_html=True)
    st.markdown(_model_step(6, "RED ZONE", result.get("red_zone_engine") or {}), unsafe_allow_html=True)
    st.markdown(_model_step(7, "THIRD DOWN", result.get("third_down_engine") or {}), unsafe_allow_html=True)
    st.markdown(_model_step(8, "TURNOVER VOLATILITY", result.get("turnover_engine") or {}), unsafe_allow_html=True)
    st.markdown(_model_step(9, "GAME-DAY ENVIRONMENT", result.get("environment_engine") or {}), unsafe_allow_html=True)
    st.markdown(_model_step(10, "HISTORICAL MATCHUP CONTEXT", result.get("history_engine") or {}), unsafe_allow_html=True)
    st.markdown(_model_step(11, "CURRENT FORM + SCHEDULE STRENGTH", result.get("form_strength_engine") or {}), unsafe_allow_html=True)
    st.markdown(_cert_step(result), unsafe_allow_html=True)
    st.markdown(_final(result), unsafe_allow_html=True)

    st.markdown("### Full-slate scan")
    editor = st.data_editor(
        _line_board(games, identity, float(line)),
        use_container_width=True,
        hide_index=True,
        key=f"cfb_ou_v17_board_{day}",
    )
    try:
        records = editor.to_dict("records")
    except Exception:
        records = list(editor) if isinstance(editor, list) else []

    selected_lines: dict[str, float] = {}
    for row in records:
        if not bool(row.get("Use")):
            continue
        row_identity = _clean(row.get("Identity"))
        try:
            row_line = float(row.get("Analysis Line"))
        except Exception:
            continue
        if row_identity:
            selected_lines[row_identity] = row_line

    if st.button(
        f"Run clean-page O/U scan for {len(selected_lines)} selected game(s)",
        key=f"cfb_ou_v17_scan_{day}",
        type="primary",
        disabled=not bool(selected_lines),
    ):
        rows, scan_diag = runtime_slate.scan_slate(games, day, selected_lines)
        ranked = final_model.rank_slate(rows, limit=5)
        st.session_state[f"cfb_ou_v17_top5_{day}"] = ranked
        st.session_state[f"cfb_ou_v17_scan_diag_{day}"] = scan_diag

    top5 = st.session_state.get(f"cfb_ou_v17_top5_{day}") or []
    scan_diag = st.session_state.get(f"cfb_ou_v17_scan_diag_{day}") or {}
    if scan_diag:
        st.caption(
            f"{int(scan_diag.get('games_analyzed') or 0)} analyzed • "
            f"{int(scan_diag.get('step12_certified_games') or 0)} Step-12 certified • "
            f"{len(scan_diag.get('errors') or [])} errors"
        )
    for rank, row in enumerate(top5, start=1):
        game_row = row.get("game") or {}
        final_row = row.get("final") or {}
        raw_row = row.get("raw") or {}
        st.markdown(
            f"**#{rank} {game_row.get('away_team')} @ {game_row.get('home_team')} — "
            f"{final_row.get('selection') or raw_row.get('model_lean') or 'PASS'}** "
            f"• projected total {_num(raw_row.get('projected_total'),1)}"
        )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Clean O/U page received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MARKET",
    "MODEL_VERSION",
    "_step1",
    "_step2",
    "render_cfb_hub",
    "render_over_under_hub",
]
