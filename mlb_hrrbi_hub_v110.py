"""MLB H+R+RBI V1.0.10 — Step 7 recent form + component quality.

Presentation/audit wrapper around verified H+R+RBI V1.0.9 Steps 1-6.
Strongest-threshold cards retain every verified layer and add a fail-safe recent
form panel built only from the official MLB game logs already attached to each
H+R+RBI finalist by V1.0:
- L5/L10 actual H+R+RBI average,
- L5/L10 hit rate at the currently selected threshold (2+/3+/4+/5+),
- L5/L10 actual Hit / Run / RBI component averages,
- recent combined-total sequence (most recent first),
- transparent trend + consistency labels,
- current Monte Carlo xH/xR/xRBI component mix.

Model firewall: Step 7 is descriptive/audit only. The underlying V1.0 model
already applies its own tightly capped recent-form blend before simulation.
This wrapper does not add, re-apply or modify any recent-form weight. Candidate
selection, H/R/RBI rates, Monte Carlo, threshold probabilities, ranking,
confidence and fair odds remain unchanged. Missing logs are labeled unavailable.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import mlb_hrrbi_hub_v109 as prior

MODEL_VERSION = "H+R+RBI V1.0.10"
base = prior.base
core = prior.core

# Capture the verified Steps 1-6 card after importing V1.0.9. V1.0.9 also
# patches the Step-4 pitch-share helper, so that validation remains active.
_BASE_CARD = base._card


def _sf(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _game_total(row):
    if not isinstance(row, dict):
        return 0.0
    return (
        (_sf(row.get("h"), 0.0) or 0.0)
        + (_sf(row.get("r"), 0.0) or 0.0)
        + (_sf(row.get("rbi"), 0.0) or 0.0)
    )


def _window_summary(logs, n, threshold):
    rows = [x for x in list(logs or []) if isinstance(x, dict)][-int(n):]
    if not rows:
        return {"available": False, "games": 0}

    games = len(rows)
    totals = [_game_total(x) for x in rows]
    hits = [(_sf(x.get("h"), 0.0) or 0.0) for x in rows]
    runs = [(_sf(x.get("r"), 0.0) or 0.0) for x in rows]
    rbis = [(_sf(x.get("rbi"), 0.0) or 0.0) for x in rows]
    threshold_hits = sum(1 for value in totals if value >= float(threshold))

    return {
        "available": True,
        "games": games,
        "avg_total": sum(totals) / games,
        "avg_h": sum(hits) / games,
        "avg_r": sum(runs) / games,
        "avg_rbi": sum(rbis) / games,
        "threshold_hits": threshold_hits,
        "threshold_rate": threshold_hits / games,
        "totals": totals,
    }


def _trend_label(l5, l10):
    if not l5.get("available") or not l10.get("available"):
        return "DATA LIMITED", "limited"
    if l5.get("games", 0) < 3 or l10.get("games", 0) < 6:
        return "LIMITED SAMPLE", "limited"
    delta = float(l5.get("avg_total", 0.0)) - float(l10.get("avg_total", 0.0))
    if delta >= 0.55:
        return "TRENDING UP", "good"
    if delta <= -0.55:
        return "TRENDING DOWN", "tough"
    return "STABLE", "neutral"


def _form_grade(l5, l10, threshold):
    """Descriptive recent-form label only; never feeds model/ranking."""
    if not l5.get("available") or not l10.get("available"):
        return "DATA LIMITED", "limited"
    if l5.get("games", 0) < 3 or l10.get("games", 0) < 6:
        return "LIMITED SAMPLE", "limited"

    r5 = float(l5.get("threshold_rate", 0.0))
    r10 = float(l10.get("threshold_rate", 0.0))
    a5 = float(l5.get("avg_total", 0.0))
    a10 = float(l10.get("avg_total", 0.0))

    # Threshold-relative, descriptive rules. No arbitrary sportsbook/model input.
    avg_edge = ((a5 + a10) / 2.0) - float(threshold)
    score = 0
    if r5 >= 0.80:
        score += 2
    elif r5 >= 0.60:
        score += 1
    elif r5 <= 0.30:
        score -= 1
    if r10 >= 0.70:
        score += 2
    elif r10 >= 0.50:
        score += 1
    elif r10 <= 0.30:
        score -= 1
    if avg_edge >= 0.65:
        score += 1
    elif avg_edge <= -0.45:
        score -= 1

    if score >= 4:
        return "ELITE RECENT FORM", "good"
    if score >= 2:
        return "STRONG RECENT FORM", "good"
    if score <= -2:
        return "COLD RECENT FORM", "tough"
    return "MIXED RECENT FORM", "neutral"


def _component_mix(sim):
    sim = sim if isinstance(sim, dict) else {}
    xh = max(_sf(sim.get("expected_h"), 0.0) or 0.0, 0.0)
    xr = max(_sf(sim.get("expected_r"), 0.0) or 0.0, 0.0)
    xrbi = max(_sf(sim.get("expected_rbi"), 0.0) or 0.0, 0.0)
    total = xh + xr + xrbi
    if total <= 0:
        return {
            "available": False,
            "xh": xh,
            "xr": xr,
            "xrbi": xrbi,
            "total": total,
            "label": "DATA LIMITED",
        }

    shares = {
        "H": xh / total,
        "R": xr / total,
        "RBI": xrbi / total,
    }
    lead = max(shares, key=shares.get)
    ordered = sorted(shares.values(), reverse=True)
    if ordered[0] - ordered[1] <= 0.10:
        label = "BALANCED COMPONENT MIX"
    else:
        label = f"{lead}-LED COMPONENT MIX"
    return {
        "available": True,
        "xh": xh,
        "xr": xr,
        "xrbi": xrbi,
        "total": total,
        "shares": shares,
        "label": label,
    }


def _fmt(value, digits=1):
    x = _sf(value, None)
    return f"{x:.{digits}f}" if x is not None else "—"


def _window_line(label, summary, threshold):
    if not summary.get("available"):
        return f"{label}: official recent game sample unavailable"
    games = int(summary.get("games") or 0)
    hits = int(summary.get("threshold_hits") or 0)
    rate = float(summary.get("threshold_rate") or 0.0) * 100.0
    return (
        f"{label}: {hits}/{games} at {int(threshold)}+ ({rate:.0f}%) • "
        f"avg H+R+RBI {_fmt(summary.get('avg_total'), 2)} • "
        f"H {_fmt(summary.get('avg_h'), 2)} • R {_fmt(summary.get('avg_r'), 2)} • "
        f"RBI {_fmt(summary.get('avg_rbi'), 2)}"
    )


def _recent_sequence(l5):
    if not l5.get("available"):
        return "Recent sequence unavailable"
    totals = list(l5.get("totals") or [])
    # V1.0 game logs are retained chronologically; show newest first for audit.
    values = []
    for value in reversed(totals):
        rounded = round(float(value), 2)
        values.append(str(int(rounded)) if abs(rounded - int(rounded)) < 1e-9 else f"{rounded:.1f}")
    return "Most recent → " + " • ".join(values)


def _recent_strip(result, threshold):
    logs = result.get("logs") or []
    l5 = _window_summary(logs, 5, threshold)
    l10 = _window_summary(logs, 10, threshold)
    form, form_cls = _form_grade(l5, l10, threshold)
    trend, trend_cls = _trend_label(l5, l10)
    mix = _component_mix(result.get("sim") or {})

    if mix.get("available"):
        shares = mix.get("shares") or {}
        component_text = (
            f"xH {mix['xh']:.2f} ({shares.get('H',0)*100:.0f}%) • "
            f"xR {mix['xr']:.2f} ({shares.get('R',0)*100:.0f}%) • "
            f"xRBI {mix['xrbi']:.2f} ({shares.get('RBI',0)*100:.0f}%) • "
            f"{mix.get('label')}"
        )
    else:
        component_text = "Model component mix unavailable — no shares inferred"

    trend_delta = None
    if l5.get("available") and l10.get("available"):
        trend_delta = float(l5.get("avg_total", 0.0)) - float(l10.get("avg_total", 0.0))
    trend_text = trend
    if trend_delta is not None:
        trend_text += f" • L5 vs L10 avg {trend_delta:+.2f}"

    return (
        '<div class="hrr110-form">'
        '<div class="hrr110-head">'
        '<span>STEP 7 • RECENT H+R+RBI FORM + COMPONENT QUALITY</span>'
        f'<b class="{form_cls}">{escape(form)}</b>'
        '</div>'
        f'<div class="hrr110-row">{escape(_window_line("L5", l5, threshold))}</div>'
        f'<div class="hrr110-row">{escape(_window_line("L10", l10, threshold))}</div>'
        f'<div class="hrr110-seq">{escape(_recent_sequence(l5))}</div>'
        '<div class="hrr110-divider"></div>'
        f'<div class="hrr110-row"><strong>Trend / consistency</strong> • '
        f'<span class="trend-{trend_cls}">{escape(trend_text)}</span></div>'
        f'<div class="hrr110-row"><strong>Monte Carlo component mix</strong> • {escape(component_text)}</div>'
        '<div class="hrr110-note">Audit/context only • V1.0 already applies its own capped recent-form blend before simulation. Step 7 does not add or re-apply recent-form weight.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr110-form{margin:7px 0 5px;padding:9px 10px;border:1px solid #4f436d;background:linear-gradient(145deg,#151022,#0a1320);border-radius:12px}
.hrr110-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.hrr110-head span{font-size:.43rem;letter-spacing:.08em;color:#c8a8ff;font-weight:950;text-transform:uppercase}.hrr110-head b{border:1px solid #594d72;border-radius:999px;padding:3px 7px;font-size:.43rem;white-space:nowrap;color:#d5c4ed}.hrr110-head b.good{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hrr110-head b.neutral{border-color:#6d5a18;background:#382f0d;color:#f1d36c}.hrr110-head b.tough{border-color:#7a3b38;background:#351514;color:#ff9d98}.hrr110-head b.limited{border-color:#465564;background:#16202a;color:#a6b3bf}
.hrr110-row{font-size:.51rem;color:#d7d2e4;line-height:1.48;margin-top:5px}.hrr110-row strong{color:#f0e9ff}.hrr110-seq{font-size:.49rem;color:#a9a0ba;line-height:1.45;margin-top:4px}.hrr110-divider{height:1px;background:#332b49;margin:7px 0 4px}.hrr110-note{font-size:.43rem;color:#7f7890;line-height:1.4;margin-top:5px}.trend-good{color:#83eab1}.trend-neutral{color:#e3d28d}.trend-tough{color:#f3a09b}.trend-limited{color:#9aa6b3}
.hrr110-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #594d72;background:#151022;color:#d1b8ff;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr110-head{align-items:flex-start}.hrr110-head b{font-size:.40rem}.hrr110-row{font-size:.49rem}}
</style>
"""

if "hrr110-form" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v110(result, rank, threshold):
    """Verified Steps 1-6 first; Step 7 can never crash or suppress the card."""
    html = _BASE_CARD(result, rank, threshold)
    try:
        strip = _recent_strip(result, threshold)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        pass
    return html


base._card = _card_v110


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr110-step-badge">📈 H+R+RBI V1.0.10 • Steps 1–7 active • recent form + component quality</div>',
        unsafe_allow_html=True,
    )
    return prior.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
