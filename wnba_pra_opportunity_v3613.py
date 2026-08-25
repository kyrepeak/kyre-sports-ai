"""WNBA PRA precision Step 1 — read-only opportunity decomposition.

This module attaches an explanatory opportunity card directly below the existing
V2.8 Minutes + Role Top-5 renderer. It reuses the already-cached V2.8 player-form
and Advanced USG tables and never feeds any value back into projection, market,
Monte Carlo, qualification, ranking, or selection logic.
"""
from __future__ import annotations

import html
import math

import pandas as pd
import streamlit as st

import wnba_pra_hub_v28 as v28
import wnba_role_v28 as role


STEP_VERSION = "PRA Precision Step 1 • Opportunity Decomposition"
_PATCH_SENTINEL = "_PRA_PRECISION_STEP1_OPPORTUNITY_INSTALLED"

CSS = r"""
<style>
.pra-opp-wrap{
  border:1px solid #31536d;
  background:linear-gradient(145deg,#0b1726,#07121e);
  border-radius:20px;padding:16px;margin:12px 0 18px;
}
.pra-opp-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}
.pra-opp-head h4{margin:0;color:#fff;font-size:1rem}
.pra-opp-tag{
  display:inline-flex;border:1px solid #2b7a5a;background:#0c2a21;color:#80efbd;
  border-radius:999px;padding:5px 9px;font-size:.54rem;font-weight:900;
  letter-spacing:.06em;text-transform:uppercase;white-space:nowrap
}
.pra-opp-sub{color:#8fa4bc;font-size:.65rem;line-height:1.5;margin-bottom:12px}
.pra-opp-card{
  border:1px solid #2b4760;background:#081522;border-radius:16px;
  padding:13px;margin:10px 0
}
.pra-opp-title{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.pra-opp-rank{color:#6bdcff;font-size:.52rem;font-weight:950;letter-spacing:.06em;text-transform:uppercase}
.pra-opp-name{color:#fff;font-size:.96rem;font-weight:950;margin-top:3px}
.pra-opp-meta{color:#8297af;font-size:.57rem;margin-top:3px;line-height:1.45}
.pra-opp-reliability{
  border:1px solid #2f6b58;background:#0d2a22;color:#8ff1c2;border-radius:999px;
  padding:4px 8px;font-size:.49rem;font-weight:950;white-space:nowrap
}
.pra-opp-reliability.med{border-color:#756227;background:#2a220e;color:#ffe189}
.pra-opp-reliability.low{border-color:#7b4343;background:#2a1316;color:#ffaaaa}
.pra-opp-section{color:#8fcdec;font-size:.54rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;margin:12px 0 7px}
.pra-opp-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}
.pra-opp-grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}
.pra-opp-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}
.pra-opp-metric{border:1px solid #243d54;background:#07121e;border-radius:11px;padding:8px;min-width:0}
.pra-opp-metric span{display:block;color:#70859d;font-size:.43rem;font-weight:950;letter-spacing:.04em;text-transform:uppercase}
.pra-opp-metric b{display:block;color:#f7fbff;font-size:.76rem;margin-top:3px;overflow-wrap:anywhere}
.pra-opp-metric small{display:block;color:#677c94;font-size:.43rem;margin-top:2px;line-height:1.35}
.pra-opp-unavailable{color:#ffe083!important}
.pra-opp-note{
  margin-top:10px;border-left:3px solid #5dd9ff;background:#0a1c2a;border-radius:0 10px 10px 0;
  padding:9px 10px;color:#97acc3;font-size:.58rem;line-height:1.5
}
.pra-opp-boundary{
  margin-top:11px;border:1px solid #37516a;border-radius:12px;padding:9px 10px;
  color:#93a9c0;font-size:.55rem;line-height:1.5
}
@media(max-width:1100px){
  .pra-opp-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pra-opp-grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}
}
@media(max-width:700px){
  .pra-opp-head,.pra-opp-title{flex-direction:column}
  .pra-opp-grid,.pra-opp-grid.three,.pra-opp-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:430px){
  .pra-opp-grid,.pra-opp-grid.three,.pra-opp-grid.two{grid-template-columns:1fr}
}
</style>
"""


def _esc(value) -> str:
    return html.escape(str(value if value is not None else "—"))


def _num(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _fmt(value, digits=1, suffix="") -> str:
    x = _num(value)
    if x is None:
        return "—"
    return f"{x:.{digits}f}{suffix}"


def _per36(stat, minutes):
    s, m = _num(stat), _num(minutes)
    if s is None or m is None or m <= 0:
        return None
    return 36.0 * s / m


def _norm_name(value) -> str:
    try:
        return role.availability._norm_name(value)
    except Exception:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _form_index(frame):
    by_pair, by_name = {}, {}
    if frame is None or getattr(frame, "empty", True):
        return by_pair, by_name
    for _, row in frame.iterrows():
        name = _norm_name(row.get("PLAYER_NAME"))
        team = str(row.get("TEAM_ABBREVIATION") or "").upper().strip()
        if not name:
            continue
        by_pair[(name, team)] = row
        by_name.setdefault(name, row)
    return by_pair, by_name


def _usage_index(frame):
    by_pair, by_name = {}, {}
    if frame is None or getattr(frame, "empty", True):
        return by_pair, by_name
    for _, row in frame.iterrows():
        name = _norm_name(row.get("PLAYER_NAME"))
        if not name:
            continue
        team = str(row.get("TEAM_ABBREVIATION") or "").upper().strip()
        by_pair[(name, team)] = row
        by_name.setdefault(name, row)
    return by_pair, by_name


def _lookup(index_pair, index_name, player, team):
    key = (_norm_name(player), str(team or "").upper().strip())
    row = index_pair.get(key)
    if row is not None:
        return row
    return index_name.get(key[0])


def _reliability(row):
    if row is None:
        return "LOW", "low"
    gp = int(_num(row.get("GP")) or 0)
    l10 = int(_num(row.get("L10_GP")) or 0)
    l5 = int(_num(row.get("L5_GP")) or 0)
    if gp >= 15 and l10 >= 8 and l5 >= 4:
        return "HIGH", ""
    if gp >= 8 and l5 >= 3:
        return "MEDIUM", "med"
    return "LOW", "low"


def _role_label(pick):
    if pick.get("starter") is True:
        return "CONFIRMED STARTER"
    status = str(pick.get("status") or "NO DESIGNATION").upper()
    if status in getattr(role, "UNCERTAIN_STATUSES", set()):
        return f"STATUS {status}"
    return "ACTIVE / ROTATION"


def _metric(label, value, note="", cls=""):
    return (
        f'<div class="pra-opp-metric"><span>{_esc(label)}</span>'
        f'<b class="{_esc(cls)}">{_esc(value)}</b>'
        + (f"<small>{_esc(note)}</small>" if note else "")
        + "</div>"
    )


def _component_share(value, pra):
    x, total = _num(value), _num(pra)
    if x is None or total is None or total <= 0:
        return "—"
    return f"{100.0*x/total:.0f}%"


def _render_player(rank, pick, form_row, usage_row, usage_source):
    projected_min = _num(pick.get("min"))
    p = _num(pick.get("p")) or 0.0
    r = _num(pick.get("r")) or 0.0
    a = _num(pick.get("a")) or 0.0
    pra = _num(pick.get("pra")) or (p + r + a)

    season_min = form_row.get("MIN") if form_row is not None else None
    l10_min = form_row.get("L10_MIN") if form_row is not None else None
    l5_min = form_row.get("L5_MIN") if form_row is not None else None
    gp = int(_num(form_row.get("GP")) or 0) if form_row is not None else 0
    l10_gp = int(_num(form_row.get("L10_GP")) or 0) if form_row is not None else 0
    l5_gp = int(_num(form_row.get("L5_GP")) or 0) if form_row is not None else 0

    season_usg = usage_row.get("USG_PCT") if usage_row is not None else None
    l10_usg = usage_row.get("L10_USG_PCT") if usage_row is not None else None
    l5_usg = usage_row.get("L5_USG_PCT") if usage_row is not None else None
    projected_usg = pick.get("usg")

    rel, rel_cls = _reliability(form_row)
    min_delta = None
    if projected_min is not None and _num(season_min) is not None:
        min_delta = projected_min - float(season_min)

    historical = {}
    if form_row is not None:
        for window, prefix in (("SEASON", ""), ("L10", "L10_"), ("L5", "L5_")):
            historical[window] = {
                "PTS": _per36(form_row.get(f"{prefix}PTS"), form_row.get(f"{prefix}MIN")),
                "REB": _per36(form_row.get(f"{prefix}REB"), form_row.get(f"{prefix}MIN")),
                "AST": _per36(form_row.get(f"{prefix}AST"), form_row.get(f"{prefix}MIN")),
            }

    return (
        '<div class="pra-opp-card">'
        '<div class="pra-opp-title"><div>'
        f'<div class="pra-opp-rank">Rank {rank} • V2.8 Top-5 player</div>'
        f'<div class="pra-opp-name">{_esc(pick.get("name") or "Player")}</div>'
        f'<div class="pra-opp-meta">{_esc(pick.get("team") or "—")} vs {_esc(pick.get("opponent") or "—")} • {_esc(_role_label(pick))} • '
        f'{gp} season GP / {l10_gp} L10 / {l5_gp} L5</div>'
        '</div>'
        f'<span class="pra-opp-reliability {rel_cls}">DATA SAMPLE • {rel}</span></div>'

        '<div class="pra-opp-section">Minutes + role opportunity</div>'
        '<div class="pra-opp-grid">'
        + _metric("Projected minutes", _fmt(projected_min,1), "existing V2.8 input")
        + _metric("Season minutes", _fmt(season_min,1))
        + _metric("L10 minutes", _fmt(l10_min,1))
        + _metric("L5 minutes", _fmt(l5_min,1), (
            f"{min_delta:+.1f} proj vs season" if min_delta is not None else ""
        ))
        + '</div>'

        '<div class="pra-opp-section">Independent projected P / R / A build</div>'
        '<div class="pra-opp-grid">'
        + _metric("Projected PTS", _fmt(p,1), f"{_component_share(p,pra)} of projected PRA")
        + _metric("Projected REB", _fmt(r,1), f"{_component_share(r,pra)} of projected PRA")
        + _metric("Projected AST", _fmt(a,1), f"{_component_share(a,pra)} of projected PRA")
        + _metric("Projected PRA", _fmt(pra,1), "sum of projected P + R + A")
        + '</div>'

        '<div class="pra-opp-section">Per-36 opportunity profile</div>'
        '<div class="pra-opp-grid three">'
        + _metric(
            "Season /36",
            f'{_fmt(historical.get("SEASON",{}).get("PTS"),1)} P • {_fmt(historical.get("SEASON",{}).get("REB"),1)} R • {_fmt(historical.get("SEASON",{}).get("AST"),1)} A',
            "season production normalized to 36 min",
        )
        + _metric(
            "L10 /36",
            f'{_fmt(historical.get("L10",{}).get("PTS"),1)} P • {_fmt(historical.get("L10",{}).get("REB"),1)} R • {_fmt(historical.get("L10",{}).get("AST"),1)} A',
            "recent 10-game opportunity rate",
        )
        + _metric(
            "L5 /36",
            f'{_fmt(historical.get("L5",{}).get("PTS"),1)} P • {_fmt(historical.get("L5",{}).get("REB"),1)} R • {_fmt(historical.get("L5",{}).get("AST"),1)} A',
            "recent 5-game opportunity rate",
        )
        + '</div>'

        '<div class="pra-opp-section">Usage + tracking availability</div>'
        '<div class="pra-opp-grid">'
        + _metric("Projected USG", _fmt(projected_usg,1,"%"), "existing V2.8 role estimate")
        + _metric("Season / L10 / L5 USG", f"{_fmt(season_usg,1,'%')} / {_fmt(l10_usg,1,'%')} / {_fmt(l5_usg,1,'%')}", usage_source)
        + _metric("Potential assists", "UNAVAILABLE", "not invented from box score", "pra-opp-unavailable")
        + _metric("Rebound chances / touches", "UNAVAILABLE", "not invented from box score", "pra-opp-unavailable")
        + '</div>'

        '<div class="pra-opp-note"><b>Precision read:</b> minutes, role and the separate scoring/rebounding/assisting opportunity paths are exposed side-by-side so a PRA projection can be audited before the combined total is trusted. Missing official tracking fields stay unavailable instead of being replaced with fake tracking metrics.</div>'
        '</div>'
    )


def _render_opportunity(picks):
    if not picks:
        return

    try:
        form = role.player_form_table()
    except Exception:
        form = pd.DataFrame()

    try:
        usage_result = role.advanced_usage_table()
        if isinstance(usage_result, tuple):
            usage, usage_source = usage_result
        else:
            usage, usage_source = usage_result, "WNBA Advanced usage"
    except Exception:
        usage, usage_source = pd.DataFrame(), "unavailable"

    form_pair, form_name = _form_index(form)
    usage_pair, usage_name = _usage_index(usage)

    cards = []
    for rank, pick in enumerate(picks, 1):
        form_row = _lookup(form_pair, form_name, pick.get("name"), pick.get("team"))
        usage_row = _lookup(usage_pair, usage_name, pick.get("name"), pick.get("team"))
        cards.append(_render_player(rank, pick, form_row, usage_row, usage_source))

    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="pra-opp-wrap">'
        '<div class="pra-opp-head"><div><h4>🔬 PRA Precision Step 1 • Opportunity Decomposition</h4></div>'
        '<span class="pra-opp-tag">Read only • Top-5 order frozen</span></div>'
        '<div class="pra-opp-sub">Attached directly to the existing V2.8 Minutes + Role Top-5. Reuses the same verified player-form and Advanced usage tables already in the PRA chain; no new provider or model input is introduced.</div>'
        + "".join(cards)
        + '<div class="pra-opp-boundary"><b>STEP-1 BOUNDARY.</b> Descriptive/audit presentation only. Existing PRA projection math, projected minutes/usage, sportsbook transport, 5M/10M Monte Carlo, fair odds, no-vig edge, EV, qualification, production grade and Top-5 ranking are unchanged.</div>'
        + '</div>',
        unsafe_allow_html=True,
    )


def install():
    """Patch only the V2.8 Top-5 presentation hook; safe across Streamlit reruns."""
    if getattr(v28, _PATCH_SENTINEL, False):
        return

    original = v28._render_top5

    def _wrapped_top5(picks):
        original(picks)
        try:
            _render_opportunity(picks)
        except Exception:
            st.info(
                "PRA Precision Step 1 enrichment is temporarily unavailable. "
                "The frozen PRA Top-5 and all model outputs are unaffected."
            )

    v28._render_top5 = _wrapped_top5
    setattr(v28, _PATCH_SENTINEL, True)
    setattr(v28, "_PRA_PRECISION_STEP1_ORIGINAL_RENDER_TOP5", original)
