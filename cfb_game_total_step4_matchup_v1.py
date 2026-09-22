"""Universal presentation-only Step 4 Matchup surface.

Step 4 answers one question for every future CFB Game Total matchup:
"How does each offense match the opponent defense through scoring, passing,
rushing, and verified EPA/play evidence?"

This module is descriptive only. It does not change projection math,
distribution math, qualification, rankings, sportsbook influence, APIs, or
model behavior. EPA is never fabricated: when a certified value is unavailable,
the surface says so explicitly.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any, Mapping

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
STEP4_PRESENTATION_MARKER = "CFB_GAME_TOTAL_STEP4_MATCHUP_OFF_DEF_PASS_RUSH_EPA_ACTIVE"

STEP4_CSS = r"""
<style>
.gt170-step4{grid-column:1/-1!important;position:relative;border:1px solid rgba(46,217,255,.65)!important;border-radius:17px!important;background:linear-gradient(145deg,#061526 0%,#071b2c 52%,#0d1530 100%)!important;box-shadow:0 0 0 2px rgba(42,124,255,.12),0 0 30px rgba(0,216,255,.10)!important;overflow:hidden}
.gt170-step4:before{content:"";position:absolute;inset:-2px;z-index:0;border-radius:18px;padding:2px;background:linear-gradient(90deg,#19d8ff,#5478ff,#9c5cff,#3ff0b5);-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
.gt170-step4 summary,.gt170-body{position:relative;z-index:1}.gt170-step4 summary{min-height:62px!important;padding:10px 13px!important;grid-template-columns:44px minmax(0,1fr) auto!important;gap:11px!important;background:linear-gradient(90deg,rgba(6,30,53,.96),rgba(15,20,55,.92))!important}
.gt170-step4 .gt159-num{width:44px!important;height:44px!important;border-radius:11px!important;background:linear-gradient(145deg,#12d9ff,#4677ff 58%,#9b5cff)!important;color:#fff!important;box-shadow:0 0 18px rgba(39,190,255,.35)!important;font-size:17px!important}
.gt170-step4 .gt159-stepcopy b{font-size:15px!important;color:#fff!important}.gt170-step4 .gt159-stepcopy span{font-size:8px!important;color:#9eb7c8!important;margin-top:4px!important}
.gt170-body{padding:11px 12px 13px}.gt170-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.gt170-battle{border:1px solid rgba(73,190,255,.28);border-radius:12px;background:linear-gradient(145deg,rgba(4,26,47,.96),rgba(8,22,39,.98));overflow:hidden}
.gt170-head{display:grid;grid-template-columns:54px minmax(0,1fr);gap:9px;align-items:center;padding:9px;border-bottom:1px solid rgba(65,153,205,.17)}
.gt170-logo{width:50px;height:42px;object-fit:contain}.gt170-head b{display:block;color:#f3f8ff;font-size:12px}.gt170-head span{display:block;color:#7f9bad;font-size:7px;margin-top:3px}
.gt170-rows{padding:7px}.gt170-row{display:grid;grid-template-columns:82px minmax(0,1fr) minmax(0,1fr);gap:6px;align-items:center;padding:7px 5px;border-bottom:1px solid rgba(72,139,177,.14)}.gt170-row:last-child{border-bottom:0}
.gt170-row>span{color:#88a8bb;font-size:7px;font-weight:900;text-transform:uppercase}.gt170-val{padding:6px;border-radius:8px;background:rgba(5,40,62,.72);border:1px solid rgba(55,169,225,.17)}.gt170-val b{display:block;color:#eaf7ff;font-size:10px}.gt170-val small{display:block;color:#7695a8;font-size:6px;margin-top:2px}
.gt170-row.missing .gt170-val b{color:#f1c96b}.gt170-row.epa .gt170-val{background:rgba(70,36,108,.28);border-color:rgba(164,94,255,.22)}
.gt170-footer{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;margin-top:9px}
.gt170-read,.gt170-epa{border-radius:10px;padding:9px;border:1px solid rgba(77,178,229,.22);background:rgba(5,30,49,.78)}.gt170-read strong,.gt170-epa strong{display:block;color:#79e7ff;font-size:8px}.gt170-read span,.gt170-epa span{display:block;color:#a3b8c6;font-size:6.8px;line-height:1.45;margin-top:4px}
.gt170-epa{border-color:rgba(166,93,255,.25);background:rgba(56,24,86,.26)}.gt170-epa strong{color:#c59cff}
.gt170-state.ready{color:#5cf0b8}.gt170-state.check{color:#ffd36a}.gt170-state.limited{color:#ff7b86}
@media(max-width:760px){.gt170-grid,.gt170-footer{grid-template-columns:1fr}.gt170-row{grid-template-columns:72px minmax(0,1fr) minmax(0,1fr)}}
</style>
"""

_UNAVAILABLE={"","—","-","none","n/a","na","unavailable","data limited"}


def _clean(value: Any) -> str:
    return re.sub(r"\s+"," ",str(value or "")).strip()


def _float(value: Any) -> float | None:
    if value is None or isinstance(value,bool):
        return None
    if isinstance(value,(int,float)):
        return float(value)
    text=_clean(value).replace(",","").replace("%","")
    match=re.search(r"-?\d+(?:\.\d+)?",text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _usable(value: Any) -> bool:
    text=_clean(value)
    return bool(text) and text.casefold() not in _UNAVAILABLE


def _direct_metric(evidence: Mapping[str,Any], *keys: str) -> float | None:
    for key in keys:
        value=_float(evidence.get(key))
        if value is not None:
            return value
    return None


def _official_metric(
    evidence: Mapping[str,Any],
    alternatives: tuple[tuple[str,...],...],
    *,
    excludes: tuple[str,...]=(),
) -> tuple[float|None,str]:
    official=evidence.get("official_stats") or {}
    if not isinstance(official,Mapping):
        return None,""
    for key,raw in official.items():
        if not isinstance(raw,Mapping):
            continue
        label=_clean(raw.get("label") or key)
        hay=f"{key} {label}".lower()
        if any(term in hay for term in excludes):
            continue
        if not any(all(term in hay for term in terms) for terms in alternatives):
            continue
        value=_float(raw.get("value_numeric"))
        if value is None:
            value=_float(raw.get("value"))
        if value is None:
            value=_float(raw.get("display_value"))
        if value is None:
            value=_float(raw.get("stat"))
        rank=_clean(raw.get("rank"))
        return value,rank
    return None,""


def _metric(
    evidence: Mapping[str,Any],
    direct_keys: tuple[str,...],
    alternatives: tuple[tuple[str,...],...],
    *,
    excludes: tuple[str,...]=(),
) -> tuple[float|None,str]:
    direct=_direct_metric(evidence,*direct_keys)
    if direct is not None:
        return direct,""
    return _official_metric(evidence,alternatives,excludes=excludes)


def _side_metrics(evidence: Mapping[str,Any]) -> dict[str,dict[str,Any]]:
    off_points=_direct_metric(
        evidence,
        "ppg",
        "points_pg",
        "scoring_offense_pg",
        "recent_ppg",
    )
    def_points=_direct_metric(
        evidence,
        "points_allowed_pg",
        "allowed_pg",
        "scoring_defense_pg",
        "recent_points_allowed_pg",
        "recent_allowed_pg",
    )

    pass_off,pass_off_rank=_metric(
        evidence,
        ("pass_yards_pg","passing_yards_pg","passing_offense_pg"),
        (("passing offense",),("passing yards",)),
        excludes=("defense","allowed"),
    )
    pass_def,pass_def_rank=_metric(
        evidence,
        ("pass_yards_allowed_pg","passing_yards_allowed_pg","passing_defense_pg"),
        (("passing yards allowed",),("passing defense",)),
    )
    rush_off,rush_off_rank=_metric(
        evidence,
        ("rush_yards_pg","rushing_yards_pg","rushing_offense_pg"),
        (("rushing offense",),("rushing yards",)),
        excludes=("defense","allowed"),
    )
    rush_def,rush_def_rank=_metric(
        evidence,
        ("rush_yards_allowed_pg","rushing_yards_allowed_pg","rushing_defense_pg"),
        (("rushing yards allowed",),("rushing defense",)),
    )
    epa_off,epa_off_rank=_metric(
        evidence,
        ("epa_per_play","offensive_epa_per_play","epa_play"),
        (("epa",),),
        excludes=("allowed","defense"),
    )
    epa_def,epa_def_rank=_metric(
        evidence,
        ("epa_allowed_per_play","defensive_epa_per_play","epa_per_play_allowed"),
        (("epa",),),
        excludes=("offense",),
    )
    return {
        "points_offense":{"value":off_points,"rank":""},
        "points_defense":{"value":def_points,"rank":""},
        "pass_offense":{"value":pass_off,"rank":pass_off_rank},
        "pass_defense":{"value":pass_def,"rank":pass_def_rank},
        "rush_offense":{"value":rush_off,"rank":rush_off_rank},
        "rush_defense":{"value":rush_def,"rank":rush_def_rank},
        "epa_offense":{"value":epa_off,"rank":epa_off_rank},
        "epa_defense":{"value":epa_def,"rank":epa_def_rank},
    }


def _fmt(value: Any, *, signed: bool=False) -> str:
    number=_float(value)
    if number is None:
        return "—"
    return f"{number:+.2f}" if signed else f"{number:.1f}"


def _rank(rank: Any) -> str:
    text=_clean(rank)
    return f"Rank {text}" if text else "Current sample"


def _row(
    label: str,
    offense: Mapping[str,Any],
    defense: Mapping[str,Any],
    *,
    epa: bool=False,
) -> dict[str,Any]:
    off=offense.get("value")
    allowed=defense.get("value")
    complete=off is not None and allowed is not None
    return {
        "label":label,
        "offense_value":off,
        "defense_value":allowed,
        "offense_rank":_clean(offense.get("rank")),
        "defense_rank":_clean(defense.get("rank")),
        "complete":complete,
        "epa":epa,
    }


def _battle(
    offense_identity: Mapping[str,Any],
    defense_identity: Mapping[str,Any],
    offense_evidence: Mapping[str,Any],
    defense_evidence: Mapping[str,Any],
) -> dict[str,Any]:
    om=_side_metrics(offense_evidence)
    dm=_side_metrics(defense_evidence)
    rows=[
        _row("Off vs Def",om["points_offense"],dm["points_defense"]),
        _row("Passing",om["pass_offense"],dm["pass_defense"]),
        _row("Rushing",om["rush_offense"],dm["rush_defense"]),
        _row("EPA / Play",om["epa_offense"],dm["epa_defense"],epa=True),
    ]
    core_complete=sum(1 for row in rows[:3] if row["complete"])
    total_complete=sum(1 for row in rows if row["complete"])
    return {
        "offense_team":_clean(offense_identity.get("team") or offense_evidence.get("team")) or "Offense",
        "defense_team":_clean(defense_identity.get("team") or defense_evidence.get("team")) or "Defense",
        "logo":_clean(offense_identity.get("logo") or offense_evidence.get("logo")),
        "rows":rows,
        "core_complete":core_complete,
        "total_complete":total_complete,
        "epa_complete":rows[-1]["complete"],
    }


def build_step4_contract(
    identity: Mapping[str,Any] | None,
    away: Mapping[str,Any] | None,
    home: Mapping[str,Any] | None,
) -> dict[str,Any]:
    identity=identity or {}
    away=away or {}
    home=home or {}
    ai=identity.get("away") if isinstance(identity.get("away"),Mapping) else {}
    hi=identity.get("home") if isinstance(identity.get("home"),Mapping) else {}

    away_battle=_battle(ai,hi,away,home)
    home_battle=_battle(hi,ai,home,away)
    core_total=away_battle["core_complete"]+home_battle["core_complete"]
    total_complete=away_battle["total_complete"]+home_battle["total_complete"]

    names_ready=_usable(away_battle["offense_team"]) and _usable(home_battle["offense_team"])
    if not names_ready or core_total == 0:
        state="DATA LIMITED"
    elif total_complete == 8:
        state="READY"
    else:
        state="CHECK"

    coverage=total_complete/8.0
    epa_ready=away_battle["epa_complete"] and home_battle["epa_complete"]
    if epa_ready:
        epa_note="Verified EPA/play is available for both directions."
    else:
        epa_note=(
            "Verified EPA/play is not available for both teams from the current certified "
            "source, so Step 4 leaves EPA blank instead of fabricating it."
        )

    return {
        "state":state,
        "ready":state=="READY",
        "away_offense_vs_home_defense":away_battle,
        "home_offense_vs_away_defense":home_battle,
        "coverage":coverage,
        "epa_ready":epa_ready,
        "epa_note":epa_note,
        "sportsbook_projection_influence":SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_projection":MAY_MODIFY_PROJECTION,
    }


def _battle_html(battle: Mapping[str,Any], testid: str) -> str:
    logo=_clean(battle.get("logo"))
    logo_html=(
        f'<img class="gt170-logo" src="{escape(logo)}" alt="{escape(_clean(battle.get("offense_team")))} logo"/>'
        if logo else '<span style="font-size:24px">🏈</span>'
    )
    rows=[]
    for row in battle.get("rows") or []:
        complete=bool(row.get("complete"))
        cls=(" epa" if row.get("epa") else "")+(" missing" if not complete else "")
        off=_fmt(row.get("offense_value"),signed=bool(row.get("epa")))
        deff=_fmt(row.get("defense_value"),signed=bool(row.get("epa")))
        rows.append(
            f'<div class="gt170-row{cls}">'
            f'<span>{escape(_clean(row.get("label")))}</span>'
            f'<div class="gt170-val"><b>{escape(off)}</b><small>{escape(_rank(row.get("offense_rank")))}</small></div>'
            f'<div class="gt170-val"><b>{escape(deff)}</b><small>{escape(_rank(row.get("defense_rank")))}</small></div>'
            '</div>'
        )
    return f"""
<div class="gt170-battle" data-testid="{escape(testid)}">
  <div class="gt170-head">
    <div>{logo_html}</div>
    <div><b>{escape(_clean(battle.get('offense_team')))} Offense</b><span>vs {escape(_clean(battle.get('defense_team')))} Defense • offense value ↔ defense allowance</span></div>
  </div>
  <div class="gt170-rows">{''.join(rows)}</div>
</div>"""


def render_step4_html(
    status: str,
    identity: Mapping[str,Any] | None,
    away: Mapping[str,Any] | None,
    home: Mapping[str,Any] | None,
) -> str:
    contract=build_step4_contract(identity,away,home)
    state=_clean(contract.get("state"))
    state_css="ready" if state=="READY" else "limited" if state=="DATA LIMITED" else "check"
    coverage=float(contract.get("coverage") or 0.0)
    read=(
        f"{int(round(coverage*8))}/8 directional matchup cells are verified. "
        "This is a current-sample matchup read only; frozen projection math is unchanged."
    )
    return f"""
<details class="gt159-step gt170-step4 {state_css}" data-testid="gt157-step-4" data-step4-state="{escape(state)}">
  <summary>
    <span class="gt159-num">4</span>
    <span class="gt159-stepcopy"><b>Matchup</b><span>Off vs Def · Pass · Rush · EPA</span></span>
    <span class="gt159-state gt170-state {state_css}">{escape(state)}</span>
  </summary>
  <div class="gt159-stepbody gt170-body">
    <div class="gt170-grid">
      {_battle_html(contract['away_offense_vs_home_defense'],'gt170-step4-away-off-home-def')}
      {_battle_html(contract['home_offense_vs_away_defense'],'gt170-step4-home-off-away-def')}
    </div>
    <div class="gt170-footer">
      <div class="gt170-read" data-testid="gt170-step4-matchup-read"><strong>⚔ MATCHUP READ</strong><span>{escape(read)}</span></div>
      <div class="gt170-epa" data-testid="gt170-step4-epa-integrity"><strong>◈ EPA INTEGRITY</strong><span>{escape(_clean(contract.get('epa_note')))}</span></div>
    </div>
  </div>
</details>"""


__all__=[
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_CSS",
    "STEP4_PRESENTATION_MARKER",
    "build_step4_contract",
    "render_step4_html",
]
