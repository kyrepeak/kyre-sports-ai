"""Presentation-only Step 1 Team Identity accordion for CFB Game Total.

This module owns no projections, probabilities, qualification, ranking, odds,
or model behavior. It converts already-available display identity/evidence into
one universal Step 1 field contract and renders the expanded accordion card.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

STEP1_REQUIRED_FIELDS = (
    "logo",
    "team",
    "mascot",
    "conference",
    "classification",
    "record",
    "rank",
    "head_coach",
    "home_away",
    "season",
    "identity_verified",
)

STEP1_CSS = r"""
<style>
.gt165-step1{grid-column:1/-1!important;position:relative;border:1px solid rgba(39,216,208,.72)!important;border-left:4px solid #45f0ad!important;border-radius:14px!important;background:linear-gradient(140deg,#071d2c,#081827 57%,#0c1429)!important;box-shadow:0 0 24px rgba(39,216,208,.10),inset 0 0 0 1px rgba(86,183,255,.05)!important;overflow:hidden}
.gt165-step1[open]{box-shadow:0 0 32px rgba(39,216,208,.13),0 12px 26px rgba(0,0,0,.20)!important}
.gt165-step1 summary{min-height:58px!important;padding:10px 12px!important;grid-template-columns:38px minmax(0,1fr) auto!important;gap:11px!important}
.gt165-step1 .gt159-num{width:38px!important;height:38px!important;border-radius:12px!important;background:linear-gradient(145deg,rgba(35,225,181,.30),rgba(20,117,113,.22))!important;box-shadow:0 0 18px rgba(69,240,173,.18)!important;font-size:15px!important}
.gt165-step1 .gt159-stepcopy b{font-size:14px!important;letter-spacing:.01em}.gt165-step1 .gt159-stepcopy span{font-size:10px!important;color:#9eb6c9!important;margin-top:3px!important}
.gt165-step1-body{padding:0 12px 13px!important}
.gt165-schema-strip{display:flex;align-items:center;gap:7px;padding:8px 10px;margin:0 0 10px;border:1px solid rgba(72,180,224,.24);border-radius:10px;background:rgba(7,42,61,.72);color:#b7d4e7;font-size:9px;font-weight:800;letter-spacing:.015em;line-height:1.4}
.gt165-schema-strip strong{display:grid;place-items:center;width:20px;height:20px;flex:0 0 20px;border-radius:50%;background:rgba(39,216,208,.16);color:#63ece3}
.gt165-team-pair{display:grid;grid-template-columns:minmax(0,1fr) 42px minmax(0,1fr);gap:9px;align-items:stretch}
.gt165-vs{display:grid;place-items:center;color:#bcd5e8;font-size:11px;font-weight:1000;letter-spacing:.08em}.gt165-vs:before,.gt165-vs:after{content:"";display:block;width:1px;height:32%;background:linear-gradient(transparent,rgba(69,240,173,.55),transparent)}
.gt165-idcard{position:relative;min-width:0;padding:12px;border:1px solid rgba(71,190,220,.34);border-radius:12px;background:radial-gradient(circle at 14% 0%,rgba(39,216,208,.09),transparent 31%),linear-gradient(145deg,#082235,#071a2a);overflow:hidden}
.gt165-idcard.home{background:radial-gradient(circle at 86% 0%,rgba(86,183,255,.10),transparent 31%),linear-gradient(145deg,#081d32,#071a2a);border-color:rgba(86,183,255,.42)}
.gt165-idcard:after{content:"";position:absolute;inset:auto -18% -48% 28%;height:120px;border:1px solid rgba(69,240,173,.06);border-radius:50%;pointer-events:none}
.gt165-idtop{display:flex;align-items:center;gap:10px}.gt165-idlogo,.gt165-idlogo-fallback{width:62px;height:62px;flex:0 0 62px;object-fit:contain;filter:drop-shadow(0 6px 14px rgba(0,0,0,.35))}
.gt165-idlogo-fallback{display:grid;place-items:center;border-radius:14px;background:#102d40;color:#9bd7ff;font-weight:1000;font-size:18px;filter:none}
.gt165-idcopy{min-width:0;flex:1}.gt165-idcopy b{display:block;color:#f5f9fd;font-size:14px;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt165-idcopy span{display:block;color:#98b0c2;font-size:10px;margin-top:4px}
.gt165-sidechip{align-self:flex-start;padding:4px 8px;border-radius:999px;border:1px solid rgba(86,183,255,.42);background:rgba(31,111,160,.13);color:#8ed9ff;font-size:8px;font-weight:950;white-space:nowrap}
.gt165-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:9px}.gt165-chip{padding:4px 8px;border-radius:999px;border:1px solid rgba(39,216,208,.30);background:rgba(19,112,113,.14);color:#a5e7e3;font-size:8px;font-weight:900}.gt165-chip.class{border-color:rgba(169,104,255,.38);background:rgba(95,51,143,.16);color:#dec8ff}
.gt165-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:10px}.gt165-field{min-width:0;padding:7px 8px;border:1px solid rgba(80,153,192,.15);border-radius:8px;background:rgba(7,34,50,.72)}.gt165-field span{display:block;color:#7795aa;font-size:8px;text-transform:uppercase;letter-spacing:.04em}.gt165-field b{display:block;color:#edf5fb;font-size:10px;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gt165-verify{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px;padding-top:9px;border-top:1px solid rgba(92,159,193,.16)}.gt165-verify span{font-size:8px;color:#88a0b4}.gt165-verify b{padding:5px 9px;border-radius:999px;border:1px solid rgba(69,240,173,.50);background:rgba(16,117,77,.18);color:#68f1b7;font-size:8px;white-space:nowrap}.gt165-verify b.check{border-color:rgba(255,210,77,.48);background:rgba(126,91,16,.18);color:#ffd85a}
.gt165-missing{margin-top:8px;color:#d6b965;font-size:8px;line-height:1.4}
@media(max-width:620px){.gt165-team-pair{grid-template-columns:1fr}.gt165-vs{display:none}.gt165-idlogo,.gt165-idlogo-fallback{width:48px;height:48px;flex-basis:48px}.gt165-fields{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


_UNAVAILABLE = {
    "",
    "—",
    "-",
    "n/a",
    "na",
    "none",
    "unavailable",
    "mascot unavailable",
    "conference unavailable",
    "fbs/fcs unavailable",
    "head coach unavailable",
    "record unavailable",
}


def _usable(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value)
    text = _clean(value)
    return bool(text) and text.casefold() not in _UNAVAILABLE


def _format_mapping(value: Mapping[str, Any]) -> str:
    if {"wins", "losses"} <= set(value):
        wins = int(value.get("wins") or 0)
        losses = int(value.get("losses") or 0)
        ties = int(value.get("ties") or 0)
        return f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    return ""


def _nested(mapping: Mapping[str, Any], key: str) -> Any:
    value = mapping.get(key)
    return value if value not in (None, "", [], {}) else None


def _pick(*values: Any) -> str:
    for value in values:
        if isinstance(value, Mapping):
            text = _format_mapping(value)
        else:
            text = _clean(value)
        if _usable(text):
            return text
    return ""


def _side_value(
    side: str,
    identity_side: Mapping[str, Any],
    evidence_side: Mapping[str, Any],
    display_game: Mapping[str, Any],
    *aliases: str,
) -> str:
    nested = display_game.get(side)
    nested_side = nested if isinstance(nested, Mapping) else {}
    for alias in aliases:
        value = _pick(
            identity_side.get(alias),
            evidence_side.get(alias),
            display_game.get(f"{side}_{alias}"),
            nested_side.get(alias),
        )
        if value:
            return value
    return ""


def _season(side: str, identity_side: Mapping[str, Any], evidence_side: Mapping[str, Any], display_game: Mapping[str, Any]) -> str:
    explicit = _side_value(side, identity_side, evidence_side, display_game, "season", "season_year", "year")
    if explicit:
        return explicit
    for key in ("game_date", "date", "start_date", "kickoff_iso", "start_time_utc"):
        raw = _clean(display_game.get(key))
        if len(raw) >= 4 and raw[:4].isdigit():
            return raw[:4]
    return ""


def build_team_identity_contract(
    side: str,
    identity_side: Mapping[str, Any] | None,
    evidence_side: Mapping[str, Any] | None,
    display_game: Mapping[str, Any] | None,
) -> dict[str, Any]:
    identity_side = identity_side or {}
    evidence_side = evidence_side or {}
    display_game = display_game or {}

    team = _side_value(side, identity_side, evidence_side, display_game, "team", "team_name", "display_name", "school", "name")
    mascot = _side_value(side, identity_side, evidence_side, display_game, "mascot", "nickname", "team_nickname")
    conference = _side_value(side, identity_side, evidence_side, display_game, "conference", "conference_name", "conf")
    classification = _side_value(side, identity_side, evidence_side, display_game, "classification", "division_context", "subdivision", "division", "level", "fbs_fcs")
    record = _side_value(side, identity_side, evidence_side, display_game, "record", "record_text", "record_summary", "overall_record", "season_record")
    rank = _side_value(side, identity_side, evidence_side, display_game, "rank", "ranking", "ap_rank", "cfp_rank", "coaches_rank")
    head_coach = _side_value(side, identity_side, evidence_side, display_game, "head_coach", "coach", "coach_name")
    logo = _side_value(side, identity_side, evidence_side, display_game, "logo", "logo_url")
    team_id = _side_value(side, identity_side, evidence_side, display_game, "team_id", "espn_team_id")
    season = _season(side, identity_side, evidence_side, display_game)
    exact_identity = bool(identity_side.get("exact_identity")) and team_id.isdigit() and bool(logo)

    contract: dict[str, Any] = {
        "logo": logo,
        "team": team,
        "mascot": mascot,
        "conference": conference,
        "classification": classification,
        "record": record,
        "rank": rank,
        "head_coach": head_coach,
        "home_away": side.upper(),
        "season": season,
        "team_id": team_id,
        "identity_verified": exact_identity,
    }
    missing = [
        field for field in STEP1_REQUIRED_FIELDS
        if field != "identity_verified" and not _usable(contract.get(field))
    ]
    if not exact_identity:
        missing.append("identity_verified")
    contract["missing_fields"] = missing
    contract["profile_complete"] = not missing
    contract["field_count"] = len(STEP1_REQUIRED_FIELDS) - len(missing)
    contract["field_total"] = len(STEP1_REQUIRED_FIELDS)
    return contract


def build_step1_contract(
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
    display_game: Mapping[str, Any] | None,
) -> dict[str, Any]:
    identity = identity or {}
    away_contract = build_team_identity_contract("away", identity.get("away") or {}, away or {}, display_game or {})
    home_contract = build_team_identity_contract("home", identity.get("home") or {}, home or {}, display_game or {})
    return {
        "away": away_contract,
        "home": home_contract,
        "ready": bool(away_contract["profile_complete"] and home_contract["profile_complete"]),
        "identity_verified": bool(away_contract["identity_verified"] and home_contract["identity_verified"]),
    }


def _logo_html(team: Mapping[str, Any]) -> str:
    name = _clean(team.get("team")) or "Team"
    logo = _clean(team.get("logo"))
    if logo:
        return f'<img class="gt165-idlogo" src="{escape(logo)}" alt="{escape(name)} logo">'
    initials = "".join(word[:1] for word in name.split() if word)[:2].upper() or "CF"
    return f'<div class="gt165-idlogo-fallback">{escape(initials)}</div>'


def _display(value: Any, fallback: str = "Unavailable") -> str:
    if isinstance(value, Mapping):
        text = _format_mapping(value)
    else:
        text = _clean(value)
    return text if _usable(text) else fallback


def _team_card(team: Mapping[str, Any], *, home_side: bool) -> str:
    missing = team.get("missing_fields") or []
    missing_html = ""
    if missing:
        readable = ", ".join(str(field).replace("_", " ").title() for field in missing)
        missing_html = f'<div class="gt165-missing">Needs data: {escape(readable)}</div>'
    verify_label = "✓ IDENTITY VERIFIED" if team.get("identity_verified") else "⚠ VERIFY IDENTITY"
    verify_class = "" if team.get("identity_verified") else "check"
    return f"""
<div class="gt165-idcard {'home' if home_side else ''}" data-testid="gt165-step1-{'home' if home_side else 'away'}">
  <div class="gt165-idtop">
    {_logo_html(team)}
    <div class="gt165-idcopy"><b>{escape(_display(team.get('team'), 'Team unavailable'))}</b><span>{escape(_display(team.get('mascot'), 'Mascot unavailable'))}</span></div>
    <span class="gt165-sidechip">{escape(_display(team.get('home_away')))}</span>
  </div>
  <div class="gt165-chips">
    <span class="gt165-chip">{escape(_display(team.get('conference'), 'Conference unavailable'))}</span>
    <span class="gt165-chip class">{escape(_display(team.get('classification'), 'FBS/FCS unavailable'))}</span>
  </div>
  <div class="gt165-fields">
    <div class="gt165-field"><span>🏆 Record</span><b>{escape(_display(team.get('record')))}</b></div>
    <div class="gt165-field"><span>📊 Rank</span><b>{escape(_display(team.get('rank')))}</b></div>
    <div class="gt165-field"><span>👤 Head Coach</span><b>{escape(_display(team.get('head_coach')))}</b></div>
    <div class="gt165-field"><span>📅 Season</span><b>{escape(_display(team.get('season')))}</b></div>
  </div>
  <div class="gt165-verify"><span>{int(team.get('field_count') or 0)}/{int(team.get('field_total') or 0)} identity fields</span><b class="{verify_class}">{verify_label}</b></div>
  {missing_html}
</div>"""


def render_step1_html(
    status: str,
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
    display_game: Mapping[str, Any] | None,
) -> str:
    contract = build_step1_contract(identity, away, home, display_game)
    away_team, home_team = contract["away"], contract["home"]
    shown = "READY" if contract["ready"] else "CHECK"
    state = "ready" if contract["ready"] else "check"
    summary = (
        f"{_display(away_team.get('team'), 'Away')} • {_display(away_team.get('conference'), 'Conference ?')} • "
        f"{_display(away_team.get('classification'), 'FBS/FCS ?')} | "
        f"{_display(home_team.get('team'), 'Home')} • {_display(home_team.get('conference'), 'Conference ?')} • "
        f"{_display(home_team.get('classification'), 'FBS/FCS ?')}"
    )
    schema = "Logo • Team • Mascot • Conference • FBS/FCS • Record • Rank • Coach • Home/Away • Season • Identity Verified"
    return f"""
<details class="gt159-step gt165-step1 {state}" data-testid="gt157-step-1" open>
  <summary>
    <span class="gt159-num">1</span>
    <span class="gt159-stepcopy"><b>Team Identity</b><span>{escape(summary)}</span></span>
    <span class="gt159-state {state}">{escape(shown)}</span>
  </summary>
  <div class="gt159-stepbody gt165-step1-body">
    <div class="gt165-schema-strip"><strong>i</strong><span>{escape(schema)}</span></div>
    <div class="gt165-team-pair">
      {_team_card(away_team, home_side=False)}
      <div class="gt165-vs">VS</div>
      {_team_card(home_team, home_side=True)}
    </div>
  </div>
</details>"""


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP1_CSS",
    "STEP1_REQUIRED_FIELDS",
    "build_step1_contract",
    "build_team_identity_contract",
    "render_step1_html",
]
