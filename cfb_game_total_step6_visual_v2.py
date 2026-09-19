"""CFB Game Total Step 6 visual parity V2.

Additive presentation-only successor to permanently frozen V184 Step 6.
All scoring evidence, coverage, grades, insights, sportsbook isolation, and
projection-safety values come from cfb_game_total_step6_scoring_v1.

This module changes HTML/CSS only. It must never fetch data, mutate model
outputs, or replace the certified Step 6 normalized contract.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import cfb_game_total_step6_scoring_v1 as frozen

MODEL_VERSION = "CFB GAME TOTAL STEP 6 • V185 VISUAL PARITY V2"
FROZEN_DATA_OWNER = "cfb_game_total_step6_scoring_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

STEP6_PRESENTATION_MARKER = frozen.STEP6_PRESENTATION_MARKER
STEP6_DATA_MARKER = frozen.STEP6_DATA_MARKER
STEP6_DEPLOYMENT_MARKER = frozen.STEP6_DEPLOYMENT_MARKER
STEP6_VISUAL_MARKER = "CFB_GAME_TOTAL_STEP6_V185_VISUAL_PARITY_ACTIVE"
STEP6_VISUAL_PARITY_MARKER = "CFB_GAME_TOTAL_STEP6_TARGET_MOCK_PARITY_ACTIVE"

build_step6_contract = frozen.build_step6_contract

_METRICS = (
    ("pass_explosive_rate", "EXPLOSIVE PASS RATE", "🏈"),
    ("rush_explosive_rate", "EXPLOSIVE RUSH RATE", "🏃"),
    ("overall_explosive_rate", "OVERALL EXPLOSIVE RATE", "📊"),
    ("scoring_ops_pg", "SCORING OPS / GAME", "🏆"),
    ("scoring_op_conversion", "SCORING-OPPORTUNITY CONVERSION", "🎯"),
    ("red_zone_td_rate", "RED-ZONE TD RATE", "🧱"),
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(value: Any) -> str:
    number = _float(value)
    return "—" if number is None else f"{100.0 * number:.0f}%"


def _value(key: str, value: Any) -> str:
    number = _float(value)
    if number is None:
        return "—"
    if key == "scoring_ops_pg":
        return f"{number:.1f}"
    return f"{100.0 * number:.0f}%"


def _team_row(identity: Mapping[str, Any], side: str) -> dict[str, Any]:
    raw = identity.get(side) if isinstance(identity.get(side), Mapping) else {}
    return dict(raw or {})


def _team_name(
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    side: str,
) -> str:
    return frozen._team_name(identity, profile, side)


def _record(
    profile: Mapping[str, Any],
    game: Mapping[str, Any],
    side: str,
) -> str:
    return frozen._record(profile, game, side) or "Record unavailable"


def _conference(
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    side: str,
) -> str:
    return frozen._conference(identity, profile, side) or "NCAAF"


def _logo_url(identity: Mapping[str, Any], side: str) -> str:
    return _clean(_team_row(identity, side).get("logo"))


def _logo_html(identity: Mapping[str, Any], side: str, css_class: str) -> str:
    name = _clean(_team_row(identity, side).get("team")) or side.title()
    logo = _logo_url(identity, side)
    if logo:
        return (
            f'<img class="{css_class}" src="{escape(logo)}" '
            f'alt="{escape(name)} logo">'
        )
    initials = "".join(part[:1] for part in name.split() if part)[:2].upper() or "CF"
    return f'<div class="{css_class} fallback">{escape(initials)}</div>'


def _game_context(game: Mapping[str, Any]) -> str:
    date_text = _clean(game.get("game_date") or game.get("date"))[:10] or "GAME DAY"
    kickoff = _clean(
        game.get("kickoff_et") or game.get("kickoff") or game.get("start_time")
    ) or "Time TBD"
    venue = _clean(game.get("venue") or game.get("venue_name")) or "Venue unavailable"
    broadcast = _clean(game.get("broadcast")) or "Broadcast unavailable"
    return f"""
<div class="gt185-s6-gamecontext">
  <span>{escape(date_text)}</span>
  <b>{escape(kickoff)}</b>
  <small>{escape(venue)}</small>
  <em>{escape(broadcast)}</em>
</div>"""


def _team_header(
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    game: Mapping[str, Any],
    side: str,
) -> str:
    name = _team_name(identity, profile, side)
    return f"""
<div class="gt185-s6-team {side}">
  {_logo_html(identity, side, "gt185-s6-logo")}
  <div class="gt185-s6-teamcopy">
    <small>{side.upper()}</small>
    <b>{escape(name)}</b>
    <span>{escape(_record(profile, game, side))}</span>
    <em>{escape(_conference(identity, profile, side))}</em>
  </div>
</div>"""


def _metric_status(key: str, value: Any, *, defense: bool) -> str:
    number = _float(value)
    if number is None:
        return "DATA LIMITED"
    if key == "pass_explosive_rate":
        hi, mid = 0.17, 0.12
    elif key == "rush_explosive_rate":
        hi, mid = 0.20, 0.14
    elif key == "overall_explosive_rate":
        hi, mid = 0.18, 0.12
    elif key == "scoring_ops_pg":
        hi, mid = 5.2, 4.0
    elif key == "scoring_op_conversion":
        hi, mid = 0.72, 0.58
    else:
        hi, mid = 0.64, 0.52

    if defense:
        if number <= mid:
            return "STOUT"
        if number <= hi:
            return "LIMITING"
        return "PRESSURE POINT"
    if number >= hi:
        return "STRONG"
    if number >= mid:
        return "ABOVE AVG"
    return "UNDER PRESSURE"


def _defense_label(key: str) -> str:
    return {
        "pass_explosive_rate": "EXPLOSIVE PASS RATE ALLOWED",
        "rush_explosive_rate": "EXPLOSIVE RUSH RATE ALLOWED",
        "overall_explosive_rate": "Big-play susceptibility",
        "scoring_ops_pg": "SCORING OPPORTUNITIES ALLOWED",
        "scoring_op_conversion": "SCORING-OPPORTUNITY CONVERSION ALLOWED",
        "red_zone_td_rate": "Red-zone TD rate allowed",
    }.get(key, key.replace("_", " ").upper())


def _metric_card(
    key: str,
    label: str,
    icon: str,
    value: Any,
    *,
    defense: bool,
    counted_ready: bool,
) -> str:
    state = _metric_status(key, value, defense=defense)
    ready = counted_ready and _float(value) is not None
    testid = (
        ' data-testid="gt184-step6-stat-tile"'
        if not defense
        else ' data-testid="gt185-step6-defense-tile"'
    )
    ready_attr = f' data-ready="{str(ready).lower()}"' if not defense else ""
    display_label = _defense_label(key) if defense else label
    tone = "defense" if defense else "offense"
    return f"""
<div class="gt185-s6-metric {tone}"{testid}{ready_attr}>
  <div class="gt185-s6-metriclabel"><span>{icon}</span><small>{escape(display_label)}</small></div>
  <b>{escape(_value(key, value))}</b>
  <em>{escape(state)}</em>
</div>"""


def _battle_pair_html(
    contract: Mapping[str, Any],
    identity: Mapping[str, Any],
    index: int,
) -> str:
    battle = (contract.get("battles") or [])[index - 1]
    offense = battle.get("offense") or {}
    defense = battle.get("defense") or {}
    offense_name = _clean(battle.get("offense_name")) or "Offense"
    defense_name = _clean(battle.get("defense_name")) or "Defense"
    offense_side = _clean(battle.get("side")) or ("away" if index == 1 else "home")
    defense_side = "home" if offense_side == "away" else "away"

    offense_cards = []
    defense_cards = []
    for key, label, icon in _METRICS:
        pair_ready = _float(offense.get(key)) is not None and _float(defense.get(key)) is not None
        offense_cards.append(
            _metric_card(
                key,
                label,
                icon,
                offense.get(key),
                defense=False,
                counted_ready=pair_ready,
            )
        )
        defense_cards.append(
            _metric_card(
                key,
                label,
                icon,
                defense.get(key),
                defense=True,
                counted_ready=pair_ready,
            )
        )

    return f"""
<section class="gt185-s6-battle" data-testid="gt184-step6-battle-{index}">
  <div class="gt185-s6-battlelabel">MATCHUP {index} • SCORING CREATION VS PREVENTION</div>
  <div class="gt185-s6-battlepair">
    <div class="gt185-s6-panel offense">
      <div class="gt185-s6-panelhead">
        {_logo_html(identity, offense_side, "gt185-s6-panel-logo")}
        <div><small>SCORING CREATION</small><b>{escape(offense_name)}</b>
        <span>Explosive creation • scoring chances • finishing</span></div>
      </div>
      <div class="gt184-s6-tilegrid gt185-s6-tilegrid">
        {''.join(offense_cards)}
      </div>
    </div>
    <div class="gt185-s6-panel defense">
      <div class="gt185-s6-panelhead">
        {_logo_html(identity, defense_side, "gt185-s6-panel-logo")}
        <div><small>SCORING PREVENTION</small><b>{escape(defense_name)}</b>
        <span>Explosive resistance • opportunity denial • red-zone defense</span></div>
      </div>
      <div class="gt185-s6-defensegrid">
        {''.join(defense_cards)}
      </div>
    </div>
  </div>
</section>"""


def _environment_html(contract: Mapping[str, Any]) -> str:
    chance = _float(contract.get("expected_scoring_chances"))
    cells = (
        ("Away Creation Grade", contract.get("away_creation_grade"), "grade"),
        ("Home Creation Grade", contract.get("home_creation_grade"), "grade"),
        ("Explosive Play Environment", contract.get("explosive_environment"), ""),
        ("Red-Zone Finishing Environment", contract.get("red_zone_environment"), ""),
        ("Projected Scoring Chances", "—" if chance is None else f"{chance:.1f}", ""),
        ("Big-Play Volatility", contract.get("big_play_volatility"), "warn"),
    )
    return '<div class="gt184-s6-env gt185-s6-env">' + "".join(
        f'<div class="{escape(tone)}"><small>{escape(_clean(label))}</small>'
        f'<b>{escape(_clean(value) or "—")}</b></div>'
        for label, value, tone in cells
    ) + "</div>"


def _insights_html(contract: Mapping[str, Any]) -> str:
    confidence = int(contract.get("data_confidence") or 0)
    return f"""
<div class="gt184-s6-insights gt185-s6-insights">
  <div class="gt185-s6-insight read">
    <small>🎯 MATCHUP READ</small>
    <b>{escape(_clean(contract.get("matchup_read")) or "DATA LIMITED")}</b>
    <span>Both offenses are evaluated against the opposing scoring-prevention profile.</span>
  </div>
  <div class="gt185-s6-insight accel">
    <small>🚀 BIGGEST ACCELERATOR</small>
    <b>{escape(_clean(contract.get("accelerator")) or "Unavailable")}</b>
    <span>Largest verified creation-vs-prevention advantage in the completed-game sample.</span>
  </div>
  <div class="gt185-s6-insight brake">
    <small>🛑 BIGGEST SUPPRESSOR</small>
    <b>{escape(_clean(contract.get("suppressor")) or "Unavailable")}</b>
    <span>Strongest verified scoring resistance in the matchup.</span>
  </div>
  <div class="gt185-s6-insight ou">
    <small>📊 O/U IMPACT</small>
    <b>{escape(_clean(contract.get("ou_impact")) or "NEUTRAL")}</b>
    <span>Direction is driven by verified Step 6 scoring evidence; sportsbook total is not an input.</span>
  </div>
  <div class="gt185-s6-insight confidence">
    <small>🛡️ DATA CONFIDENCE</small>
    <b>{confidence}%</b>
    <span>PBP coverage plus completed-game sample strength.</span>
  </div>
</div>"""


def render_step6_html(
    status: str,
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any] | None = None,
) -> str:
    contract = frozen.build_step6_contract(
        identity,
        away,
        home,
        display_game,
        evidence=evidence,
    )
    state = _clean(contract.get("state")) or "DATA LIMITED"
    coverage = int(contract.get("coverage") or 0)
    ready_tiles = int(contract.get("ready_tiles") or 0)
    summary_state = "ready" if state == "READY" else "check"
    body_class = "ready" if state == "READY" else "limited"

    return f"""
<details class="gt184-step6 gt185-step6 {body_class}" data-testid="gt157-step-6"
 data-step6-marker="{STEP6_PRESENTATION_MARKER}"
 data-step6-data-marker="{STEP6_DATA_MARKER}"
 data-step6-visual-marker="{STEP6_VISUAL_MARKER}"
 data-step6-visual-parity-marker="{STEP6_VISUAL_PARITY_MARKER}"
 data-step6-deployment-marker="{STEP6_DEPLOYMENT_MARKER}"
 data-step6-state="{escape(state)}"
 data-step6-coverage="{coverage}"
 data-step6-ready-tiles="{ready_tiles}" open>
<style>{_CSS}</style>
<summary>
  <span class="gt185-s6-num">6</span>
  <span class="gt185-s6-summarycopy">
    <b><i>✦</i> STEP 6 — <span class="gt185-s6-legacytitle">💥 Scoring Creation</span></b>
    <span>Explosive plays • red zone • scoring opportunities • finishing ability</span>
  </span>
  <span class="gt185-s6-state {summary_state}">{escape(state)}</span>
  <span class="gt185-s6-chevron">⌃</span>
</summary>
<div class="gt185-s6-body">
  <div class="gt185-s6-head">
    <div class="gt185-s6-title">
      <small>STEP 6 • SCORING CREATION</small>
      <h3>How well can each team create and finish real scoring chances?</h3>
    </div>
    <div class="gt185-s6-chips">
      <span class="green">{escape(state)}</span>
      <span>{coverage}% SCORING COVERAGE</span>
      <span>MULTI-SOURCE VERIFIED</span>
      <span class="purple">SPORTSBOOK INFLUENCE 0.0%</span>
    </div>
  </div>

  <div class="gt185-s6-matchup">
    {_team_header(identity, away, display_game, "away")}
    <div class="gt185-s6-vs">VS</div>
    {_team_header(identity, home, display_game, "home")}
    {_game_context(display_game)}
  </div>

  {_battle_pair_html(contract, identity, 1)}
  {_battle_pair_html(contract, identity, 2)}

  <div class="gt185-s6-sectiontitle">
    <div><span>▥</span><b>SCORING ENVIRONMENT</b></div>
    <small>Composite view of scoring creation, prevention, and expected opportunities.</small>
  </div>
  {_environment_html(contract)}

  {_insights_html(contract)}

  <div class="gt185-s6-integrity">
    NCAA PRIMARY • SPORTSDATAVERSE PBP • RUNTIME SNAPSHOT IDENTITY • MODEL SAFE •
    PROJECTION MUTATION OFF • SPORTSBOOK INFLUENCE 0.0%
  </div>
</div>
</details>
"""


_CSS = r"""
.gt184-step6.gt185-step6{
  grid-column:1/-1!important;width:100%!important;max-width:none!important;box-sizing:border-box;
  margin:10px 0 12px;border:2px solid rgba(25,226,235,.78);border-left:5px solid #19e2eb;
  border-right:4px solid #7546ff;border-radius:19px;overflow:hidden;color:#f4f8ff;
  background:linear-gradient(135deg,#06131f 0%,#071826 42%,#0a1223 72%,#0b1021 100%);
  box-shadow:0 0 0 1px rgba(73,120,255,.22),0 0 34px rgba(0,221,235,.16),0 0 40px rgba(108,63,255,.12);
}
.gt185-step6 summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:52px minmax(0,1fr) auto 24px;align-items:center;gap:13px;padding:13px 16px;background:linear-gradient(90deg,rgba(13,108,174,.22),rgba(8,32,51,.82) 48%,rgba(76,40,171,.18));border-bottom:1px solid rgba(78,190,225,.22)}
.gt185-step6 summary::-webkit-details-marker{display:none}.gt185-s6-num{display:flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:12px;background:linear-gradient(145deg,#087cbb,#0c49a7);box-shadow:inset 0 0 14px rgba(74,226,255,.25),0 0 15px rgba(19,164,246,.25);font-size:1.05rem;font-weight:950}
.gt185-s6-summarycopy{min-width:0}.gt185-s6-summarycopy b{display:block;color:#f9fbff;font-size:1.02rem;font-weight:950;letter-spacing:.035em}.gt185-s6-summarycopy b i{color:#4cecff;font-style:normal;text-shadow:0 0 12px rgba(76,236,255,.8)}.gt185-s6-legacytitle{color:#f9fbff}.gt185-s6-summarycopy span{display:block;color:#a8bbcf;font-size:.74rem;margin-top:3px}
.gt185-s6-state{padding:7px 14px;border-radius:999px;border:1px solid rgba(58,239,177,.72);background:rgba(14,112,78,.22);color:#5cf0bc;font-size:.72rem;font-weight:950;white-space:nowrap;box-shadow:0 0 14px rgba(50,231,174,.08)}.gt185-s6-state.check{border-color:rgba(246,205,73,.62);color:#f2d264;background:rgba(120,86,8,.2)}.gt185-s6-chevron{font-size:1.1rem;color:#e4f3ff;text-align:center}
.gt185-s6-body{padding:15px;background:radial-gradient(circle at 0 0,rgba(0,199,228,.09),transparent 34%),radial-gradient(circle at 100% 0,rgba(111,67,255,.10),transparent 32%),linear-gradient(180deg,#061521,#07131e)}
.gt185-s6-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.gt185-s6-title small{color:#ff9e6d;font-size:.66rem;font-weight:950;letter-spacing:.12em}.gt185-s6-title h3{margin:6px 0 0;color:#f7fbff;font-size:1.18rem;line-height:1.35;font-weight:900}
.gt185-s6-chips{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:7px;max-width:56%}.gt185-s6-chips span{padding:7px 11px;border-radius:999px;border:1px solid rgba(57,203,220,.46);background:rgba(5,44,61,.82);color:#74e8f0;font-size:.64rem;font-weight:950;white-space:nowrap}.gt185-s6-chips .green{color:#58efb9;border-color:rgba(88,239,185,.63);background:rgba(15,105,75,.22)}.gt185-s6-chips .purple{color:#d7a5ff;border-color:rgba(194,118,255,.6);background:rgba(74,40,116,.25)}
.gt185-s6-matchup{display:grid;grid-template-columns:minmax(0,1fr) 58px minmax(0,1fr) minmax(145px,.55fr);align-items:center;gap:11px;margin-top:14px;padding:14px;border:1px solid rgba(55,168,213,.42);border-radius:15px;background:linear-gradient(110deg,rgba(4,36,52,.94),rgba(6,26,41,.96) 54%,rgba(18,29,47,.94));box-shadow:inset 0 0 18px rgba(29,142,204,.06)}
.gt185-s6-team{display:flex;align-items:center;gap:11px;min-width:0}.gt185-s6-team.home{justify-content:flex-end;flex-direction:row-reverse;text-align:right}.gt185-s6-logo{width:64px;height:64px;object-fit:contain;flex:0 0 64px;filter:drop-shadow(0 0 9px rgba(99,188,255,.18))}.gt185-s6-logo.fallback{display:flex;align-items:center;justify-content:center;border-radius:15px;background:#102d40;color:#78dfff;font-size:1.05rem;font-weight:950}
.gt185-s6-teamcopy{min-width:0}.gt185-s6-teamcopy small{display:block;color:#48dff1;font-size:.65rem;font-weight:950;letter-spacing:.07em}.gt185-s6-team.home .gt185-s6-teamcopy small{color:#ff9a52}.gt185-s6-teamcopy b{display:block;color:#f9fbff;font-size:1.17rem;line-height:1.08;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt185-s6-teamcopy span{display:block;color:#a3b6c8;font-size:.7rem;margin-top:4px}.gt185-s6-teamcopy em{display:inline-block;margin-top:4px;color:#93a8ba;font-size:.65rem;font-style:normal}
.gt185-s6-vs{display:flex;align-items:center;justify-content:center;width:48px;height:48px;margin:auto;border-radius:50%;border:1px solid rgba(60,171,234,.52);background:linear-gradient(145deg,#092b3d,#081b2c);color:#a9d6ee;font-size:.78rem;font-weight:950;box-shadow:0 0 16px rgba(55,177,239,.08)}
.gt185-s6-gamecontext{align-self:stretch;display:flex;flex-direction:column;justify-content:center;padding-left:12px;border-left:1px solid rgba(84,167,208,.28)}.gt185-s6-gamecontext span{color:#c5d3df;font-size:.66rem}.gt185-s6-gamecontext b{color:#f7fbff;font-size:.83rem;margin-top:2px}.gt185-s6-gamecontext small{color:#9eb0c0;font-size:.64rem;margin-top:4px}.gt185-s6-gamecontext em{color:#8198ab;font-size:.61rem;font-style:normal;margin-top:3px}
.gt185-s6-battle{margin-top:14px;padding:0;border-radius:15px}.gt185-s6-battlelabel{padding:0 2px 7px;color:#849caf;font-size:.62rem;font-weight:950;letter-spacing:.08em}.gt185-s6-battlepair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.gt185-s6-panel{border-radius:15px;overflow:hidden;background:linear-gradient(145deg,#071d2a,#071622);box-shadow:inset 0 0 24px rgba(24,138,197,.04)}.gt185-s6-panel.offense{border:2px solid rgba(33,205,232,.64);box-shadow:0 0 18px rgba(20,195,227,.06)}.gt185-s6-panel.defense{border:2px solid rgba(255,133,74,.64);box-shadow:0 0 18px rgba(255,117,52,.05)}
.gt185-s6-panelhead{display:flex;align-items:center;gap:10px;padding:12px 13px;border-bottom:1px solid rgba(96,162,201,.22);background:rgba(4,28,43,.68)}.gt185-s6-panel.defense .gt185-s6-panelhead{background:rgba(43,25,20,.38);border-bottom-color:rgba(235,122,69,.2)}.gt185-s6-panel-logo{width:39px;height:39px;object-fit:contain;flex:0 0 39px}.gt185-s6-panel-logo.fallback{display:flex;align-items:center;justify-content:center;border-radius:10px;background:#0e3345;color:#78eaff;font-size:.75rem;font-weight:950}
.gt185-s6-panelhead small{display:block;color:#58e4ef;font-size:.61rem;font-weight:950;letter-spacing:.06em}.gt185-s6-panel.defense .gt185-s6-panelhead small{color:#ff9d5a}.gt185-s6-panelhead b{display:block;color:#f6fbff;font-size:.93rem;margin-top:2px}.gt185-s6-panelhead span{display:block;color:#8fa5b7;font-size:.63rem;margin-top:2px}
.gt184-s6-tilegrid.gt185-s6-tilegrid,.gt185-s6-defensegrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:10px}.gt185-s6-metric{min-width:0;padding:10px;border-radius:11px;border:1px solid rgba(70,158,201,.34);background:linear-gradient(145deg,#0a2534,#081a28);position:relative;overflow:hidden}.gt185-s6-metric.offense:before,.gt185-s6-metric.defense:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px}.gt185-s6-metric.offense:before{background:#19dce5}.gt185-s6-metric.defense{border-color:rgba(238,128,70,.34);background:linear-gradient(145deg,#15242b,#111b25)}.gt185-s6-metric.defense:before{background:#ff834c}
.gt185-s6-metriclabel{display:flex;align-items:center;gap:6px;min-height:29px}.gt185-s6-metriclabel span{font-size:.8rem}.gt185-s6-metriclabel small{color:#b2c4d2;font-size:.6rem;font-weight:950;line-height:1.22}.gt185-s6-metric b{display:block;color:#f8fbff;font-size:1.25rem;line-height:1;margin-top:6px}.gt185-s6-metric em{display:inline-block;margin-top:8px;padding:4px 8px;border-radius:999px;border:1px solid rgba(71,230,190,.5);background:rgba(19,108,79,.2);color:#58eebe;font-size:.56rem;font-style:normal;font-weight:950}.gt185-s6-metric.defense em{border-color:rgba(246,197,72,.52);background:rgba(118,83,10,.17);color:#f3cf61}
.gt185-s6-sectiontitle{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:16px 2px 7px}.gt185-s6-sectiontitle div{display:flex;align-items:center;gap:7px}.gt185-s6-sectiontitle div span{color:#48dff1;font-size:1rem}.gt185-s6-sectiontitle b{color:#f7fbff;font-size:.79rem;letter-spacing:.08em}.gt185-s6-sectiontitle small{color:#859bae;font-size:.63rem;text-align:right}
.gt184-s6-env.gt185-s6-env{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid rgba(75,92,232,.48);border-radius:13px;background:linear-gradient(100deg,#081c2a,#0c1728 72%,#11142c);overflow:hidden;box-shadow:inset 0 0 20px rgba(98,70,242,.05)}.gt185-s6-env>div{padding:11px 8px;text-align:center;border-right:1px solid rgba(111,134,180,.18)}.gt185-s6-env>div:last-child{border-right:0}.gt185-s6-env small{display:block;color:#9bacc0;font-size:.57rem;text-transform:uppercase;line-height:1.2}.gt185-s6-env b{display:block;color:#f7fbff;font-size:.9rem;margin-top:5px}.gt185-s6-env .grade b{color:#55e9bd;font-size:1.2rem}.gt185-s6-env .warn b{color:#f4cf5f}
.gt184-s6-insights.gt185-s6-insights{display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:9px;margin-top:11px}.gt185-s6-insight{padding:12px;border:1px solid rgba(74,154,198,.35);border-radius:13px;background:linear-gradient(145deg,#091f2d,#081923)}.gt185-s6-insight small{display:block;color:#9bb0c0;font-size:.6rem;font-weight:950;letter-spacing:.04em}.gt185-s6-insight b{display:block;color:#f8fbff;font-size:.83rem;margin-top:5px;line-height:1.26}.gt185-s6-insight span{display:block;color:#93a5b4;font-size:.63rem;line-height:1.42;margin-top:6px}.gt185-s6-insight.read{grid-row:span 2;border-color:rgba(54,226,188,.46);box-shadow:inset 3px 0 0 #45e6b9}.gt185-s6-insight.read b{color:#57e8ba;font-size:.94rem}.gt185-s6-insight.accel{border-color:rgba(45,169,244,.5)}.gt185-s6-insight.accel b{color:#79cfff}.gt185-s6-insight.brake{border-color:rgba(255,83,91,.46)}.gt185-s6-insight.brake b{color:#ff747d}.gt185-s6-insight.ou{border-color:rgba(29,218,224,.48)}.gt185-s6-insight.ou b{color:#54e8e9}.gt185-s6-insight.confidence{border-color:rgba(72,162,240,.48)}.gt185-s6-insight.confidence b{font-size:1.35rem;color:#79cfff}
.gt185-s6-integrity{margin-top:12px;padding:10px 12px;border:1px solid rgba(62,131,168,.22);border-radius:10px;background:#06131e;color:#7f94a7;font-size:.55rem;font-weight:900;text-align:center;letter-spacing:.07em}
@media(max-width:900px){.gt185-s6-head{display:block}.gt185-s6-chips{max-width:none;justify-content:flex-start;margin-top:10px}.gt185-s6-matchup{grid-template-columns:1fr 50px 1fr}.gt185-s6-gamecontext{grid-column:1/-1;border-left:0;border-top:1px solid rgba(84,167,208,.28);padding:10px 0 0}.gt185-s6-battlepair{grid-template-columns:1fr}.gt184-s6-tilegrid.gt185-s6-tilegrid,.gt185-s6-defensegrid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:760px){.gt185-step6 summary{grid-template-columns:43px minmax(0,1fr) auto 18px;padding:11px}.gt185-s6-num{width:41px;height:41px}.gt185-s6-summarycopy b{font-size:.88rem}.gt185-s6-summarycopy span{font-size:.64rem}.gt185-s6-matchup{grid-template-columns:1fr 42px 1fr}.gt185-s6-logo{width:52px;height:52px;flex-basis:52px}.gt185-s6-teamcopy b{font-size:.96rem}.gt184-s6-tilegrid.gt185-s6-tilegrid,.gt185-s6-defensegrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt184-s6-env.gt185-s6-env{grid-template-columns:repeat(3,minmax(0,1fr))}.gt184-s6-insights.gt185-s6-insights{grid-template-columns:1fr 1fr}.gt185-s6-insight.read{grid-column:1/-1;grid-row:auto}}
@media(max-width:430px){.gt185-s6-body{padding:10px}.gt185-step6 summary{grid-template-columns:38px minmax(0,1fr) auto;padding:9px;gap:8px}.gt185-s6-chevron{display:none}.gt185-s6-num{width:36px;height:36px;font-size:.86rem}.gt185-s6-summarycopy b{font-size:.76rem}.gt185-s6-summarycopy span{font-size:.55rem}.gt185-s6-state{padding:5px 8px;font-size:.57rem}.gt185-s6-title h3{font-size:.98rem}.gt185-s6-chips span{font-size:.56rem;padding:5px 8px}.gt185-s6-matchup{grid-template-columns:1fr 32px 1fr;padding:10px;gap:7px}.gt185-s6-logo{width:42px;height:42px;flex-basis:42px}.gt185-s6-teamcopy b{font-size:.78rem}.gt185-s6-teamcopy span,.gt185-s6-teamcopy em{font-size:.55rem}.gt185-s6-vs{width:30px;height:30px;font-size:.61rem}.gt184-s6-tilegrid.gt185-s6-tilegrid,.gt185-s6-defensegrid{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:7px}.gt185-s6-metric{padding:8px}.gt185-s6-metriclabel small{font-size:.52rem}.gt185-s6-metric b{font-size:1.02rem}.gt185-s6-metric em{font-size:.49rem;padding:3px 6px}.gt184-s6-env.gt185-s6-env{grid-template-columns:repeat(2,minmax(0,1fr))}.gt184-s6-insights.gt185-s6-insights{grid-template-columns:1fr}.gt185-s6-sectiontitle{display:block}.gt185-s6-sectiontitle small{display:block;text-align:left;margin-top:4px}}
"""

__all__ = [
    "FROZEN_DATA_OWNER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP6_DATA_MARKER",
    "STEP6_DEPLOYMENT_MARKER",
    "STEP6_PRESENTATION_MARKER",
    "STEP6_VISUAL_MARKER",
    "STEP6_VISUAL_PARITY_MARKER",
    "build_step6_contract",
    "render_step6_html",
]
