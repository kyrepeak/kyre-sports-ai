"""Presentation-only Step 2 Team Profile accordion for CFB Game Total.

Uses the already-built display evidence for both teams and does not alter any
projection, distribution, qualification, ranking, odds, API, or model behavior.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

STEP2_REQUIRED_FIELDS = (
    "team",
    "sample_games",
    "ppg",
    "allowed_pg",
    "point_diff_pg",
    "recent_form",
)

STEP2_CSS = r"""
<style>
.gt166-step2{grid-column:1/-1!important;position:relative;border:1px solid rgba(97,150,255,.54)!important;border-left:4px solid #6b9cff!important;border-radius:14px!important;background:linear-gradient(145deg,#081a2e,#081623 58%,#0a1428)!important;box-shadow:0 0 22px rgba(63,119,255,.08)!important;overflow:hidden}
.gt166-step2[open]{box-shadow:0 0 30px rgba(63,119,255,.12),0 12px 24px rgba(0,0,0,.18)!important}
.gt166-step2 summary{min-height:56px!important;padding:10px 12px!important;grid-template-columns:38px minmax(0,1fr) auto!important;gap:11px!important}
.gt166-step2 .gt159-num{width:38px!important;height:38px!important;border-radius:12px!important;background:linear-gradient(145deg,rgba(77,126,255,.28),rgba(75,59,164,.18))!important;color:#a9c7ff!important;box-shadow:0 0 18px rgba(88,125,255,.14)!important;font-size:15px!important}
.gt166-step2 .gt159-stepcopy b{font-size:14px!important}.gt166-step2 .gt159-stepcopy span{font-size:10px!important;color:#93a9bc!important;margin-top:3px!important}
.gt166-step2-body{padding:0 12px 13px!important}
.gt166-schema-strip{display:flex;align-items:center;gap:7px;padding:8px 10px;margin:0 0 10px;border:1px solid rgba(95,132,255,.22);border-radius:10px;background:rgba(21,35,71,.58);color:#b8c8e8;font-size:9px;font-weight:800;line-height:1.4}
.gt166-schema-strip strong{display:grid;place-items:center;width:20px;height:20px;flex:0 0 20px;border-radius:50%;background:rgba(95,132,255,.18);color:#a8c4ff}
.gt166-team-pair{display:grid;grid-template-columns:minmax(0,1fr) 38px minmax(0,1fr);gap:9px;align-items:stretch}
.gt166-vs{display:grid;place-items:center;color:#a8b9cb;font-size:10px;font-weight:1000;letter-spacing:.07em}.gt166-vs:before,.gt166-vs:after{content:"";display:block;width:1px;height:31%;background:linear-gradient(transparent,rgba(109,149,255,.50),transparent)}
.gt166-profile{padding:11px;border:1px solid rgba(92,140,217,.28);border-radius:12px;background:linear-gradient(150deg,rgba(11,38,58,.96),rgba(8,27,43,.98));min-width:0}
.gt166-profile.home{border-color:rgba(155,104,255,.30);background:linear-gradient(150deg,rgba(19,31,62,.96),rgba(10,25,43,.98))}
.gt166-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.gt166-head b{color:#f4f8fc;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt166-record{padding:4px 8px;border-radius:999px;border:1px solid rgba(164,115,255,.30);background:rgba(101,62,170,.14);color:#dac8ff;font-size:8px;font-weight:950;white-space:nowrap}
.gt166-sample{margin-top:4px;color:#7f97ad;font-size:8px}
.gt166-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:9px}.gt166-metric{padding:8px;border:1px solid rgba(86,146,183,.15);border-radius:9px;background:rgba(7,31,47,.78)}.gt166-metric b{display:block;color:#eff6fb;font-size:13px;line-height:1}.gt166-metric span{display:block;color:#7e96aa;font-size:8px;text-transform:uppercase;letter-spacing:.04em;margin-top:4px}.gt166-metric.good b{color:#65edb8}.gt166-metric.bad b{color:#ff8b84}.gt166-metric.info b{color:#95c9ff}
.gt166-form{margin-top:8px;padding:7px 8px;border:1px solid rgba(83,147,190,.16);border-radius:8px;background:rgba(8,32,49,.58);display:flex;justify-content:space-between;gap:8px;align-items:center}.gt166-form span{color:#7f97a9;font-size:8px;text-transform:uppercase}.gt166-form b{color:#dce8f2;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gt166-footer{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:9px;padding-top:8px;border-top:1px solid rgba(87,140,174,.14)}.gt166-footer span{color:#7d92a5;font-size:8px}.gt166-footer b{padding:5px 9px;border-radius:999px;border:1px solid rgba(98,239,182,.40);background:rgba(17,102,69,.15);color:#69eeb8;font-size:8px}.gt166-footer b.check{border-color:rgba(244,206,99,.38);background:rgba(107,79,18,.15);color:#f4d46d}
.gt166-missing{margin-top:7px;color:#d4b96a;font-size:8px;line-height:1.35}
@media(max-width:620px){.gt166-team-pair{grid-template-columns:1fr}.gt166-vs{display:none}.gt166-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _usable(value: Any) -> bool:
    return _clean(value) not in {"", "—", "-", "None", "none", "Unavailable", "unavailable"}


def _sample(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def build_team_profile_contract(
    evidence: Mapping[str, Any] | None,
    identity_side: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = evidence or {}
    identity_side = identity_side or {}
    team = _clean(evidence.get("team") or identity_side.get("team") or identity_side.get("team_name"))
    sample_games = _sample(evidence.get("sample_games"))
    ppg = evidence.get("ppg")
    allowed_pg = evidence.get("allowed_pg")
    point_diff_pg = evidence.get("point_diff_pg")
    recent_form = _clean(evidence.get("recent_form"))
    record = _clean(evidence.get("record") or identity_side.get("record"))

    contract: dict[str, Any] = {
        "team": team,
        "record": record,
        "sample_games": sample_games,
        "ppg": ppg,
        "allowed_pg": allowed_pg,
        "point_diff_pg": point_diff_pg,
        "recent_form": recent_form,
    }
    missing: list[str] = []
    if not team:
        missing.append("team")
    if sample_games <= 0:
        missing.append("sample_games")
    for field in ("ppg", "allowed_pg", "point_diff_pg"):
        if evidence.get(field) is None:
            missing.append(field)
    if not _usable(recent_form):
        missing.append("recent_form")
    contract["missing_fields"] = missing
    contract["profile_complete"] = not missing
    contract["field_count"] = len(STEP2_REQUIRED_FIELDS) - len(missing)
    contract["field_total"] = len(STEP2_REQUIRED_FIELDS)
    return contract


def build_step2_contract(
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
) -> dict[str, Any]:
    identity = identity or {}
    away_contract = build_team_profile_contract(away, identity.get("away") or {})
    home_contract = build_team_profile_contract(home, identity.get("home") or {})
    return {
        "away": away_contract,
        "home": home_contract,
        "ready": bool(away_contract["profile_complete"] and home_contract["profile_complete"]),
    }


def _metric(label: str, value: Any, css: str = "") -> str:
    return f'<div class="gt166-metric {css}"><b>{escape(_num(value))}</b><span>{escape(label)}</span></div>'


def _card(team: Mapping[str, Any], *, home_side: bool) -> str:
    diff = team.get("point_diff_pg")
    diff_class = ""
    try:
        diff_class = "good" if float(diff) >= 0 else "bad"
    except (TypeError, ValueError):
        diff_class = ""

    missing = team.get("missing_fields") or []
    missing_html = ""
    if missing:
        readable = ", ".join(str(field).replace("_", " ").title() for field in missing)
        missing_html = f'<div class="gt166-missing">Needs data: {escape(readable)}</div>'

    ready = bool(team.get("profile_complete"))
    state_label = "PROFILE READY" if ready else "PROFILE CHECK"
    state_class = "" if ready else "check"
    return f"""
<div class="gt166-profile {'home' if home_side else ''}" data-testid="gt166-step2-{'home' if home_side else 'away'}">
  <div class="gt166-head">
    <b>{escape(_clean(team.get('team')) or ('Home' if home_side else 'Away'))}</b>
    <span class="gt166-record">{escape(_clean(team.get('record')) or 'Record unavailable')}</span>
  </div>
  <div class="gt166-sample">{int(team.get('sample_games') or 0)} completed games in current profile sample</div>
  <div class="gt166-metrics">
    {_metric('Points / Game', team.get('ppg'), 'info')}
    {_metric('Allowed / Game', team.get('allowed_pg'))}
    {_metric('Point Diff / Game', team.get('point_diff_pg'), diff_class)}
    <div class="gt166-metric"><b>{escape(_clean(team.get('recent_form')) or '—')}</b><span>Recent Form</span></div>
  </div>
  <div class="gt166-form"><span>Profile read</span><b>Offense • Defense • Differential • Form</b></div>
  <div class="gt166-footer"><span>{int(team.get('field_count') or 0)}/{int(team.get('field_total') or 0)} core profile fields</span><b class="{state_class}">{state_label}</b></div>
  {missing_html}
</div>"""


def render_step2_html(
    status: str,
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
) -> str:
    contract = build_step2_contract(identity, away, home)
    a, h = contract["away"], contract["home"]
    ready = bool(contract["ready"])
    shown = "READY" if ready else "CHECK"
    state = "ready" if ready else "check"
    summary = (
        f"{_clean(a.get('team')) or 'Away'} {_num(a.get('ppg'))} PPG • {_num(a.get('allowed_pg'))} allowed | "
        f"{_clean(h.get('team')) or 'Home'} {_num(h.get('ppg'))} PPG • {_num(h.get('allowed_pg'))} allowed"
    )
    schema = "Record • Sample Games • Points/Game • Allowed/Game • Point Diff/Game • Recent Form"
    return f"""
<details class="gt159-step gt166-step2 {state}" data-testid="gt157-step-2">
  <summary>
    <span class="gt159-num">2</span>
    <span class="gt159-stepcopy"><b>Team Profile</b><span>{escape(summary)}</span></span>
    <span class="gt159-state {state}">{shown}</span>
  </summary>
  <div class="gt159-stepbody gt166-step2-body">
    <div class="gt166-schema-strip"><strong>2</strong><span>{escape(schema)}</span></div>
    <div class="gt166-team-pair">
      {_card(a, home_side=False)}
      <div class="gt166-vs">VS</div>
      {_card(h, home_side=True)}
    </div>
  </div>
</details>"""


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP2_CSS",
    "STEP2_REQUIRED_FIELDS",
    "build_step2_contract",
    "build_team_profile_contract",
    "render_step2_html",
]
