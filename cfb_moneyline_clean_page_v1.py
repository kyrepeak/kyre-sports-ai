"""CFB Moneyline Clean Page V1 — presentation-only Monster dashboard.

Additive presentation layer over the permanently frozen College Football
Moneyline Step-6 stack. The certified raw/final model owners are not modified.

Presentation upgrades only:
- Phoenix, Arizona kickoff-time display,
- exact ESPN team-ID logos with fail-closed monograms,
- compact matchup hero and Quick Read,
- readable "Why the model leans" cards built only from frozen output fields,
- deep evidence collapsed into expanders,
- mobile-first visual hierarchy.

Sportsbook influence on model probability remains exactly 0.0%.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_moneyline_final_v1 as final_model
import cfb_moneyline_hub_v5 as frozen
import cfb_moneyline_slate_v1 as slate
import cfb_over_under_logo_resolver_v3 as logo_v3
import cfb_over_under_runtime_team_data_v1 as runtime_display
import cfb_schedule_v3 as schedule_v3

MODEL_VERSION = "CFB MONEYLINE CLEAN PAGE V1 • MONSTER COMPACT DASHBOARD"
MARKET = "Moneyline"
FROZEN_MONEYLINE_OWNER = "cfb_moneyline_hub_v5"
FROZEN_RAW_MODEL = "cfb_moneyline_model_v1"
FROZEN_FINAL_MODEL = "cfb_moneyline_final_v1"
ACTIVE_LOGO_RESOLVER = "cfb_over_under_logo_resolver_v3"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_PHOENIX = ZoneInfo("America/Phoenix")
_EASTERN = ZoneInfo("America/New_York")

_CSS = r"""
<style>
.cfbm-shell,.cfbm-card{box-sizing:border-box}
.cfbm-shell{margin:8px 0 12px;border:1px solid rgba(92,126,255,.30);border-radius:20px;
 background:radial-gradient(circle at 90% 0%,rgba(124,58,237,.17),transparent 22rem),
 linear-gradient(145deg,#07111e,#0a1525 58%,#0d1120);padding:15px;overflow:hidden}
.cfbm-kicker{color:#9a8cff;font-size:.58rem;font-weight:950;letter-spacing:.10em;text-transform:uppercase}
.cfbm-title{color:#f8fbff;font-size:1.52rem;font-weight:950;letter-spacing:-.03em;margin-top:3px}
.cfbm-sub{color:#91a2b8;font-size:.65rem;line-height:1.5;margin-top:5px;max-width:800px}
.cfbm-pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.cfbm-pill{border:1px solid rgba(119,140,166,.26);border-radius:999px;background:#0d1b2a;color:#b5c2d1;
 padding:5px 8px;font-size:.42rem;font-weight:900;white-space:nowrap}
.cfbm-pill.good{border-color:rgba(60,207,137,.42);background:rgba(21,92,61,.28);color:#94efbd}
.cfbm-pill.blue{border-color:rgba(62,177,255,.38);background:rgba(20,73,108,.26);color:#8dd6ff}
.cfbm-pill.purple{border-color:rgba(168,116,255,.42);background:rgba(75,41,127,.27);color:#cbb1ff}
.cfbm-pill.amber{border-color:rgba(244,191,77,.38);background:rgba(101,72,18,.27);color:#f5d47d}

.cfbm-hero{margin:10px 0;border:1px solid rgba(76,153,220,.25);border-radius:18px;background:#081522;overflow:hidden}
.cfbm-hero-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:9px 11px;
 border-bottom:1px solid rgba(76,153,220,.13)}
.cfbm-hero-head b{color:#7ed5ff;font-size:.47rem;letter-spacing:.08em}.cfbm-verified{color:#8beab7;font-size:.39rem;font-weight:950}
.cfbm-match{display:grid;grid-template-columns:minmax(0,1fr) 58px minmax(0,1fr);gap:8px;align-items:stretch;padding:11px}
.cfbm-team{display:grid;grid-template-columns:62px minmax(0,1fr);gap:9px;align-items:center;border:1px solid rgba(148,163,184,.12);
 border-radius:14px;background:linear-gradient(145deg,#0a1724,#0b1420);padding:9px;min-width:0}
.cfbm-team.home{grid-template-columns:minmax(0,1fr) 62px;text-align:right}.cfbm-team.home .cfbm-logo{grid-column:2}.cfbm-team.home .cfbm-team-copy{grid-column:1;grid-row:1}
.cfbm-logo{width:62px;height:62px;border:1px solid rgba(255,255,255,.10);border-radius:13px;background:#0e1b28;display:flex;align-items:center;justify-content:center;overflow:hidden}
.cfbm-logo img{width:53px;height:53px;object-fit:contain}.cfbm-mono{color:#dce9f3;font-size:.92rem;font-weight:950}
.cfbm-rank{color:#79d6ff;font-size:.39rem;font-weight:950;text-transform:uppercase}.cfbm-name{color:#f5f9fc;font-size:1.02rem;font-weight:950;line-height:1.1;margin-top:2px}
.cfbm-meta{color:#8195a8;font-size:.42rem;font-weight:800;line-height:1.45;margin-top:4px}.cfbm-at{display:flex;flex-direction:column;align-items:center;justify-content:center;color:#71889c;font-size:.32rem;font-weight:900}
.cfbm-at b{display:block;color:#edf5fa;font-size:1.05rem}.cfbm-context{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border-top:1px solid rgba(76,153,220,.11)}
.cfbm-context div{padding:8px 9px;border-right:1px solid rgba(76,153,220,.08);min-width:0}.cfbm-context div:last-child{border-right:0}
.cfbm-context small{display:block;color:#72889b;font-size:.29rem;font-weight:950;text-transform:uppercase}.cfbm-context strong{display:block;color:#dce8f0;font-size:.46rem;margin-top:3px;line-height:1.35}

.cfbm-section{margin-top:11px}.cfbm-section-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 1px 7px}
.cfbm-section-title b{color:#eaf2f7;font-size:.56rem;font-weight:950;letter-spacing:.07em}.cfbm-section-title span{color:#798b9d;font-size:.36rem}
.cfbm-quick{display:grid;grid-template-columns:1.35fr .9fr;gap:8px}
.cfbm-lead{border:1px solid rgba(164,112,255,.34);border-radius:15px;background:linear-gradient(145deg,rgba(71,42,118,.32),#0a1622);padding:12px}
.cfbm-lead small{display:block;color:#b9a2ff;font-size:.34rem;font-weight:950;text-transform:uppercase}.cfbm-lead h3{margin:3px 0 0;color:#fbfaff;font-size:1.18rem}.cfbm-lead strong{display:block;color:#d3c3ff;font-size:1.50rem;margin-top:4px}
.cfbm-lead p{margin:4px 0 0;color:#8f9caf;font-size:.40rem;line-height:1.45}.cfbm-grade{border:1px solid rgba(59,177,255,.25);border-radius:15px;background:#091824;padding:12px}
.cfbm-grade small{display:block;color:#77a6bf;font-size:.34rem;font-weight:950;text-transform:uppercase}.cfbm-grade b{display:block;color:#eef8fd;font-size:1.12rem;margin-top:4px}.cfbm-grade strong{display:block;color:#77d4ff;font-size:.58rem;margin-top:4px}
.cfbm-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:7px}.cfbm-metric{border:1px solid rgba(137,157,179,.14);border-radius:10px;background:#0a1620;padding:8px;min-width:0}
.cfbm-metric b{display:block;color:#e8f0f5;font-size:.60rem;line-height:1.25}.cfbm-metric span{display:block;color:#748797;font-size:.29rem;text-transform:uppercase;margin-top:3px;line-height:1.3}

.cfbm-why{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.cfbm-factor{border:1px solid rgba(130,151,172,.16);border-radius:11px;background:#0a151f;padding:8px}
.cfbm-factor small{display:block;color:#7c91a2;font-size:.28rem;font-weight:950;text-transform:uppercase}.cfbm-factor b{display:block;color:#ecf3f7;font-size:.54rem;margin-top:3px}.cfbm-factor span{display:block;color:#8699a6;font-size:.31rem;line-height:1.35;margin-top:3px}
.cfbm-factor.support{border-color:rgba(62,204,134,.31);background:rgba(17,72,51,.22)}.cfbm-factor.support b{color:#a1efc5}
.cfbm-factor.pushback{border-color:rgba(255,104,112,.30);background:rgba(90,31,37,.20)}.cfbm-factor.pushback b{color:#ffb1b6}
.cfbm-factor.caution{border-color:rgba(244,191,77,.29);background:rgba(90,67,17,.20)}.cfbm-factor.caution b{color:#f2d685}
.cfbm-factor.neutral{border-color:rgba(70,169,236,.25);background:rgba(16,58,86,.19)}.cfbm-factor.neutral b{color:#9cdbff}
.cfbm-note{margin-top:7px;border-left:3px solid #8d6cff;background:rgba(87,60,139,.13);border-radius:0 9px 9px 0;padding:8px 9px;color:#a8b1c1;font-size:.36rem;line-height:1.5}

.cfbm-top{border:1px solid rgba(134,158,180,.16);border-radius:11px;background:#0a151f;padding:9px;margin-top:6px}.cfbm-top-row{display:flex;justify-content:space-between;gap:8px;align-items:center}.cfbm-top-rank{color:#7ed7ff;font-size:.36rem;font-weight:950}.cfbm-top-team{color:#f0f5f8;font-size:.70rem;font-weight:950;margin-top:2px}.cfbm-top-prob{color:#c5b4ff;font-size:.72rem;font-weight:950}.cfbm-top-meta{color:#778c9b;font-size:.32rem;line-height:1.45;margin-top:4px}

@media(max-width:760px){
 .cfbm-shell{padding:12px}.cfbm-title{font-size:1.28rem}.cfbm-match{grid-template-columns:1fr;padding:9px}.cfbm-at{min-height:24px}
 .cfbm-team,.cfbm-team.home{grid-template-columns:54px minmax(0,1fr);text-align:left}.cfbm-team.home .cfbm-logo{grid-column:1}.cfbm-team.home .cfbm-team-copy{grid-column:2;grid-row:1}
 .cfbm-logo{width:54px;height:54px}.cfbm-logo img{width:46px;height:46px}.cfbm-context{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbm-context div:last-child{grid-column:1/-1}
 .cfbm-quick{grid-template-columns:1fr}.cfbm-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbm-why{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:430px){.cfbm-why{grid-template-columns:1fr}.cfbm-name{font-size:.90rem}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _num(value: Any, digits: int = 1, signed: bool = False) -> str:
    try:
        number = float(value)
    except Exception:
        return "—"
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number:.{digits}f}"


def _odds(value: Any) -> str:
    try:
        number = int(round(float(value)))
    except Exception:
        return "—"
    return f"+{number}" if number > 0 else str(number)


def _kickoff_datetime(game: Mapping[str, Any]) -> datetime | None:
    raw = _clean(game.get("kickoff_iso"))
    if raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=_EASTERN)
            return parsed.astimezone(_PHOENIX)
        except Exception:
            pass

    day = _clean(game.get("game_date"))
    text = _clean(game.get("kickoff_et"))
    if day and text:
        cleaned = text.replace(" ET", "").replace(" EST", "").replace(" EDT", "").strip()
        for fmt in ("%I:%M %p", "%H:%M"):
            try:
                parsed = datetime.strptime(f"{day} {cleaned}", f"%Y-%m-%d {fmt}").replace(tzinfo=_EASTERN)
                return parsed.astimezone(_PHOENIX)
            except Exception:
                pass
    return None


def _kickoff_phoenix(game: Mapping[str, Any]) -> str:
    parsed = _kickoff_datetime(game)
    if parsed is None:
        return "TBD Phoenix"
    return parsed.strftime("%I:%M %p").lstrip("0") + " Phoenix"


def _rank_prefix(value: Any) -> str:
    try:
        rank = int(value)
        return f"#{rank} " if rank > 0 else ""
    except Exception:
        return ""


def _matchup_label(game: Mapping[str, Any]) -> str:
    return (
        f"{_rank_prefix(game.get('away_rank'))}{_clean(game.get('away_team')) or 'Away'} "
        f"@ {_rank_prefix(game.get('home_rank'))}{_clean(game.get('home_team')) or 'Home'} "
        f"• {_kickoff_phoenix(game)}"
    )


def _display_game(game: Mapping[str, Any]) -> dict[str, Any]:
    """Presentation-only enrichment copy; the model always receives the original game."""
    out = dict(game)
    try:
        snapshot = runtime_display._find_snapshot(out)
        if snapshot:
            runtime_display._merge_game_snapshot(out, snapshot)
            out["moneyline_display_snapshot_enriched"] = True
    except Exception:
        pass
    return out


def _display_profiles(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fresh visible identity copies; frozen model profiles are never mutated."""
    away_out = dict(away or {})
    home_out = dict(home or {})
    try:
        snapshot = runtime_display._find_snapshot(game)
        if snapshot:
            away_snap = snapshot.get("away") or {}
            home_snap = snapshot.get("home") or {}
            if isinstance(away_snap, Mapping):
                away_out = runtime_display._profile_from_snapshot(away_out, away_snap)
            if isinstance(home_snap, Mapping):
                home_out = runtime_display._profile_from_snapshot(home_out, home_snap)
    except Exception:
        pass

    try:
        away_out = runtime_display._apply_game_event_fallback(away_out, game, "away")
        home_out = runtime_display._apply_game_event_fallback(home_out, game, "home")
    except Exception:
        pass
    return away_out, home_out


def _resolve_visuals(game: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        return logo_v3.resolve_visuals(game)
    except Exception:
        return {"away": {}, "home": {}}


def _monogram(name: str) -> str:
    tokens = [token for token in _clean(name).replace("&", " ").split() if token]
    return "".join(token[0].upper() for token in tokens[:2]) or "CFB"


def _logo_html(name: str, visual: Mapping[str, Any]) -> str:
    url = _clean(visual.get("logo"))
    if url:
        return f'<div class="cfbm-logo"><img src="{escape(url)}" alt="{escape(name)} logo"></div>'
    return f'<div class="cfbm-logo"><span class="cfbm-mono">{escape(_monogram(name))}</span></div>'


def _rank_text(profile: Mapping[str, Any], game: Mapping[str, Any], side: str) -> str:
    rank = profile.get("ap_rank")
    if rank is None:
        rank = game.get(f"{side}_rank")
    try:
        return f"#{int(rank)} AP" if rank is not None else "UNRANKED"
    except Exception:
        return "UNRANKED"


def _record_text(profile: Mapping[str, Any], game: Mapping[str, Any], side: str) -> str:
    return _clean(profile.get("record_text")) or _clean(game.get(f"{side}_record_summary")) or "Record unavailable"


def _team_hero(side: str, profile: Mapping[str, Any], game: Mapping[str, Any], visual: Mapping[str, Any]) -> str:
    name = _clean(profile.get("team")) or _clean(game.get(f"{side}_team")) or side.title()
    conference = _clean(profile.get("conference")) or _clean(game.get(f"{side}_conference")) or "Conference unavailable"
    record = _record_text(profile, game, side)
    rank = _rank_text(profile, game, side)
    home_cls = " home" if side == "home" else ""
    copy = f'''
<div class="cfbm-team-copy">
 <div class="cfbm-rank">{escape(rank)}</div>
 <div class="cfbm-name">{escape(name)}</div>
 <div class="cfbm-meta">{escape(conference)} • {escape(record)}</div>
</div>'''
    logo = _logo_html(name, visual)
    return f'<div class="cfbm-team{home_cls}">{copy}{logo}</div>' if side == "home" else f'<div class="cfbm-team{home_cls}">{logo}{copy}</div>'


def _hero(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    visuals = _resolve_visuals(game)
    verified = bool(game.get("identity_verified") and game.get("date_matches_query"))
    site = "Neutral site" if bool(game.get("neutral_site")) else "Home field"
    return f'''
<div class="cfbm-hero">
 <div class="cfbm-hero-head"><b>SELECTED MONEYLINE MATCHUP</b><span class="cfbm-verified">{'IDENTITY VERIFIED ✓' if verified else 'IDENTITY CHECK'}</span></div>
 <div class="cfbm-match">
  {_team_hero('away', away, game, visuals.get('away') or {})}
  <div class="cfbm-at"><b>@</b>MATCHUP</div>
  {_team_hero('home', home, game, visuals.get('home') or {})}
 </div>
 <div class="cfbm-context">
  <div><small>PHOENIX TIME</small><strong>{escape(_kickoff_phoenix(game))}</strong></div>
  <div><small>Venue</small><strong>{escape(_clean(game.get('venue')) or 'Venue unavailable')}</strong></div>
  <div><small>TV</small><strong>{escape(_clean(game.get('broadcast')) or 'Broadcast unavailable')}</strong></div>
  <div><small>Status</small><strong>{escape(_clean(game.get('status')) or 'Status unavailable')}</strong></div>
  <div><small>Site</small><strong>{escape(site)}</strong></div>
 </div>
</div>'''


def _winner_side(final: Mapping[str, Any]) -> str:
    side = _clean(final.get("winner_side")).lower()
    if side in {"away", "home"}:
        return side
    try:
        return "home" if float(final.get("home_win_probability_final")) >= 0.5 else "away"
    except Exception:
        return ""


def _quick_read(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not final.get("ready"):
        reasons = " • ".join(str(x) for x in final.get("reasons") or ["Final synthesis unavailable"])
        return f'<div class="cfbm-note">Final model is gated: {escape(reasons)}. Nothing is invented.</div>'

    winner = _clean(final.get("winner_team")) or "Model leader"
    winner_p = final.get("winner_probability_final")
    winner_side = _winner_side(final)
    fair = final.get("home_fair_moneyline") if winner_side == "home" else final.get("away_fair_moneyline")
    try:
        lean = abs(float(winner_p) - 0.5) * 100.0
        lean_text = f"{lean:.1f} pts vs 50%"
    except Exception:
        lean_text = "—"
    confidence = _clean(raw.get("confidence")) or "CHECK"
    grade = _clean(final.get("model_grade")) or "PASS"
    tier = _clean(final.get("model_tier")) or "PASS"
    away_name = _clean(away.get("team")) or _clean(game.get("away_team")) or "Away"
    home_name = _clean(home.get("team")) or _clean(game.get("home_team")) or "Home"
    projected_total = raw.get("projected_total_raw")

    return f'''
<div class="cfbm-section">
 <div class="cfbm-section-title"><b>⚡ QUICK READ</b><span>Final frozen model first • details later</span></div>
 <div class="cfbm-quick">
  <div class="cfbm-lead"><small>MODEL FAVORITE • PRICE-INDEPENDENT</small><h3>{escape(winner)}</h3><strong>{_pct(winner_p)}</strong><p>Fair ML {_odds(fair)} • model lean {escape(lean_text)}</p></div>
  <div class="cfbm-grade"><small>MODEL GRADE</small><b>{escape(grade)}</b><strong>{escape(tier)} • {escape(confidence)} INPUT CONFIDENCE</strong></div>
 </div>
 <div class="cfbm-metrics">
  <div class="cfbm-metric"><b>{_pct(final.get('away_win_probability_final'))}</b><span>{escape(away_name)} final P(win)</span></div>
  <div class="cfbm-metric"><b>{_pct(final.get('home_win_probability_final'))}</b><span>{escape(home_name)} final P(win)</span></div>
  <div class="cfbm-metric"><b>{_odds(final.get('away_fair_moneyline'))} / {_odds(final.get('home_fair_moneyline'))}</b><span>Fair ML • away / home</span></div>
  <div class="cfbm-metric"><b>{_num(final.get('projected_away_points'))} – {_num(final.get('projected_home_points'))}</b><span>Projected score • away / home</span></div>
  <div class="cfbm-metric"><b>{_num(final.get('projected_margin_home'), signed=True)}</b><span>Projected home margin</span></div>
  <div class="cfbm-metric"><b>{_num(projected_total)}</b><span>Projected total</span></div>
  <div class="cfbm-metric"><b>{_pct(final.get('reliability'))}</b><span>Reliability</span></div>
  <div class="cfbm-metric"><b>{_pct(final.get('feature_coverage'))}</b><span>Feature coverage</span></div>
 </div>
</div>'''


def _factor_state(delta_home: Any, winner_side: str, ready: bool = True) -> tuple[str, str, str]:
    if not ready:
        return "caution", "LIMITED", "Evidence unavailable or intentionally zero-impact."
    try:
        value = float(delta_home)
    except Exception:
        return "caution", "LIMITED", "Evidence unavailable."
    if abs(value) < 0.05:
        return "neutral", "NEUTRAL", "No meaningful directional push."
    factor_side = "home" if value > 0 else "away"
    if not winner_side:
        return "neutral", f"FAVORS {factor_side.upper()}", f"{value:+.1f} model points toward home."
    if factor_side == winner_side:
        return "support", f"SUPPORTS {factor_side.upper()}", f"{value:+.1f} model points toward home."
    return "pushback", f"PUSHES {factor_side.upper()}", f"{value:+.1f} model points toward home."


def _factor(label: str, delta_home: Any, winner_side: str, ready: bool = True, detail: str = "") -> str:
    cls, verdict, auto_detail = _factor_state(delta_home, winner_side, ready=ready)
    copy = detail or auto_detail
    return f'<div class="cfbm-factor {cls}"><small>{escape(label)}</small><b>{escape(verdict)}</b><span>{escape(copy)}</span></div>'


def _why_model(raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not raw.get("ready"):
        return '<div class="cfbm-note">WHY THE MODEL LEANS is unavailable until the frozen raw model is ready.</div>'
    comp = raw.get("components") or {}
    winner_side = _winner_side(final)

    scoring_delta = None
    recent_delta = None
    efficiency_delta = None
    try:
        scoring_delta = float(comp.get("home_base_points")) - float(comp.get("away_base_points"))
    except Exception:
        pass
    try:
        recent_delta = float(comp.get("home_recent_adjustment")) - float(comp.get("away_recent_adjustment"))
    except Exception:
        pass
    try:
        efficiency_delta = float(comp.get("home_efficiency_adjustment")) - float(comp.get("away_efficiency_adjustment"))
    except Exception:
        pass

    qb_ready = not (
        "UNVERIFIED" in _clean(comp.get("away_qb_state")).upper()
        and "UNVERIFIED" in _clean(comp.get("home_qb_state")).upper()
    )
    home_field = comp.get("home_field_points")
    neutral = bool(raw.get("neutral_site"))

    factors = [
        _factor("Scoring baseline", scoring_delta, winner_side),
        _factor("Recent scoring form", recent_delta, winner_side),
        _factor("Efficiency", efficiency_delta, winner_side),
        _factor("Turnover margin", comp.get("turnover_edge_home_points"), winner_side),
        _factor("Schedule strength", comp.get("sos_edge_home_points"), winner_side),
        _factor("Home field", 0.0 if neutral else home_field, winner_side, ready=True, detail=("Neutral site • no home-field points." if neutral else f"{_num(home_field, 1, signed=True)} frozen home-field points.")),
    ]

    qb_note = (
        "QB evidence is verified upstream and included only through the frozen Step-5 contract."
        if qb_ready
        else "QB data is unverified in the frozen model, so its impact stays exactly 0.0 points — no guessing."
    )
    return f'''
<div class="cfbm-section">
 <div class="cfbm-section-title"><b>🧠 WHY THE MODEL LEANS</b><span>Readable view of frozen Step-5 components</span></div>
 <div class="cfbm-why">{''.join(factors)}</div>
 <div class="cfbm-note">{escape(qb_note)} Green supports the final model side • red pushes the other way • blue is neutral • amber means limited.</div>
</div>'''


def _top_card(row: Mapping[str, Any]) -> str:
    game = row.get("game") or {}
    final = row.get("final") or {}
    winner = _clean(final.get("winner_team")) or "—"
    winner_side = _winner_side(final)
    fair = final.get("home_fair_moneyline") if winner_side == "home" else final.get("away_fair_moneyline")
    return f'''
<div class="cfbm-top">
 <div class="cfbm-top-row"><div><span class="cfbm-top-rank">#{int(row.get('rank') or 0)} • {escape(_clean(final.get('model_grade')) or 'PASS')}</span><div class="cfbm-top-team">{escape(winner)}</div></div><div class="cfbm-top-prob">{_pct(final.get('winner_probability_final'))}</div></div>
 <div class="cfbm-top-meta">{escape(_clean(game.get('away_team')))} @ {escape(_clean(game.get('home_team')))} • {_kickoff_phoenix(game)} • fair ML {_odds(fair)} • reliability {_pct(final.get('reliability'))}</div>
</div>'''


def _slate_rows(games: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for original in games:
        game = _display_game(original)
        rows.append({
            "Matchup": f"{game.get('away_team')} @ {game.get('home_team')}",
            "Kickoff Phoenix": _kickoff_phoenix(game),
            "Away conf": game.get("away_conference"),
            "Home conf": game.get("home_conference"),
            "Venue": game.get("venue"),
            "TV": game.get("broadcast"),
            "Status": game.get("status"),
            "NCAA ID": game.get("game_id"),
        })
    return rows


def render_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.caption(
        "🟣 CFB MONEYLINE • MONSTER COMPACT DASHBOARD V1 • PHOENIX TIME • "
        "EXACT ESPN TEAM-ID LOGOS • FROZEN STEP-6 MODEL • 0.0% SPORTSBOOK PROJECTION INFLUENCE"
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        """
<div class="cfbm-shell">
 <div class="cfbm-kicker">CFB MONEYLINE • MONSTER DASHBOARD</div>
 <div class="cfbm-title">🏆 College Football Moneyline</div>
 <div class="cfbm-sub">The certified Step-6 model stays frozen underneath. This layer only cleans up the presentation, converts kickoff display to Phoenix time, uses exact ESPN team-ID logos, and moves deep audit evidence out of the main reading lane.</div>
 <div class="cfbm-pills">
  <span class="cfbm-pill blue">PHOENIX TIME ✓</span>
  <span class="cfbm-pill blue">EXACT TEAM IDENTITY ✓</span>
  <span class="cfbm-pill purple">FROZEN FINAL MODEL ✓</span>
  <span class="cfbm-pill good">FAIR ML ✓</span>
  <span class="cfbm-pill amber">SPORTSBOOK WEIGHT 0%</span>
 </div>
</div>
""",
        unsafe_allow_html=True,
    )

    today_phoenix = datetime.now(_PHOENIX).date()
    selected = st.date_input(
        "📅 CFB Moneyline slate date",
        value=today_phoenix,
        key="cfb_moneyline_clean_v1_date",
        help="Kickoff display is converted to America/Phoenix. The certified NCAA schedule remains the slate source.",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = schedule_v3.load_with_diagnostics(selected_day)
    if not games:
        st.warning(
            "No verified FBS-scoped games were returned for this date. The frozen model remains fail-closed; no probability, fair odds, or pick is invented."
        )
        attempts = frozen.prior.frozen_step5._diag_rows(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics", expanded=False):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Moneyline matchup",
        options=list(range(len(games))),
        format_func=lambda i: _matchup_label(_display_game(games[int(i)])),
        key=f"cfb_moneyline_clean_v1_matchup_{selected_day}",
    )
    game = games[int(index)]

    # CRITICAL FREEZE BOUNDARY: analysis receives the original frozen schedule row.
    # Runtime-snapshot/logo enrichment is applied only to a separate display copy.
    selected_result = slate.analyze_game(game, selected_day)
    away = selected_result.get("away") or {}
    home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}
    team_diag = selected_result.get("team_diag") or {}
    display_game = _display_game(game)
    display_away, display_home = _display_profiles(display_game, away, home)

    st.markdown(_hero(display_game, display_away, display_home), unsafe_allow_html=True)
    st.markdown(_quick_read(display_game, away, home, raw, final), unsafe_allow_html=True)
    st.markdown(_why_model(raw, final), unsafe_allow_html=True)

    st.session_state["cfb_moneyline_final_v1_game_id"] = str(game.get("identity_key") or game.get("game_id") or "")
    st.session_state["cfb_moneyline_final_v1_selected"] = dict(final)

    with st.expander("🧪 Advanced model evidence", expanded=False):
        st.caption("Frozen Step-5 raw model + Step-6 final synthesis. Presentation only; no formula changes.")
        st.markdown(frozen.prior.frozen_step5._model_card(game, away, home, raw), unsafe_allow_html=True)
        st.markdown(frozen._final_card(game, away, home, final), unsafe_allow_html=True)
        feature_html = frozen.prior.frozen_step5._feature_panel(raw)
        if feature_html:
            st.markdown(feature_html, unsafe_allow_html=True)

    with st.expander("📚 Frozen team evidence", expanded=False):
        st.markdown(
            f"""
<div class="cfb3-section">
 <div class="cfb3-title">FROZEN TEAM EVIDENCE • MODEL AUDIT</div>
 <div class="cfb3-sub">Certified team-data values are unchanged by the Monster presentation layer.</div>
 {frozen.prior.frozen_step5.frozen_v3._team_data_diagnostics(team_diag)}
 <div class="cfb3-grid">
  {frozen.prior.frozen_step5.frozen_v3._team_card(away)}
  {frozen.prior.frozen_step5.frozen_v3._team_card(home)}
 </div>
</div>
""",
            unsafe_allow_html=True,
        )

    with st.expander(f"🗓️ Full verified slate • {selected_day} • Phoenix times", expanded=False):
        st.dataframe(_slate_rows(games), use_container_width=True, hide_index=True)

    st.markdown(
        '<div class="cfbm-section"><div class="cfbm-section-title"><b>🏆 TOP-5 MONEYLINE SCANNER</b><span>Pure frozen final win probability • no sportsbook price</span></div></div>',
        unsafe_allow_html=True,
    )
    scan_key = f"cfb_moneyline_clean_v1_top5_{selected_day}"
    scan_diag_key = f"cfb_moneyline_clean_v1_top5_diag_{selected_day}"
    if st.button(
        f"Run full {len(games)}-game Moneyline scan",
        key=f"cfb_moneyline_clean_v1_scan_{selected_day}",
        type="primary",
    ):
        with st.spinner(f"Analyzing {len(games)} verified games through the frozen Moneyline model..."):
            rows, scan_diag = slate.scan_slate(games, selected_day)
            st.session_state[scan_key] = final_model.rank_slate(rows, limit=5)
            st.session_state[scan_diag_key] = scan_diag

    top5 = st.session_state.get(scan_key) or []
    scan_diag = st.session_state.get(scan_diag_key) or {}
    if top5:
        st.caption(
            f"Scanner: {int(scan_diag.get('games_ready') or 0)} model-ready • "
            f"{int(scan_diag.get('games_gated') or 0)} gated • {len(scan_diag.get('errors') or [])} errors"
        )
        for row in top5:
            st.markdown(_top_card(row), unsafe_allow_html=True)
    else:
        st.caption("Top-5 appears only after you run the full-slate scan.")

    st.info(
        "Frozen model guarantee: raw Step 5 + final Step 6 own every probability, score, fair moneyline, calibration, and ranking value. This page changes presentation only; sportsbook projection influence remains 0.0%."
    )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"CFB Moneyline Clean Page V1 received unsupported market: {market}")
    return render_moneyline_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_LOGO_RESOLVER",
    "FROZEN_FINAL_MODEL",
    "FROZEN_MONEYLINE_OWNER",
    "FROZEN_RAW_MODEL",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_display_game",
    "_display_profiles",
    "_kickoff_phoenix",
    "_matchup_label",
    "_resolve_visuals",
    "render_cfb_hub",
    "render_moneyline_hub",
]
