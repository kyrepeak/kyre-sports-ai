"""MLB Pitcher Strikeouts O/U V1.0.15 — fail-safe Top-5 reason boxes.

Preserves V1.0.14 sportsbook transport and V1.0.11 evidence intelligence. This
version changes presentation only: Supports / Concerns are computed independently
per signal and injected into the proven V1.0.11 intelligence block. A failure in
one signal becomes N/A for that signal; it can never suppress the rest of the
Top-5 intelligence card.

Projection math, Monte Carlo, market grading, line transport, evidence score,
Top-5 candidate pool and probability ranking are unchanged.
"""
from __future__ import annotations

from textwrap import dedent
import math

import streamlit as st

import mlb_pitcher_k_hub_v1014 as v1014
import mlb_pitcher_k_hub_v1011 as v1011
import mlb_pitcher_k_hub_v109 as v109
import mlb_pitcher_k_hub_v101 as v101

engine = v1014.engine
MODEL_VERSION = "Pitcher K V1.0.15"
_base_card = v1011._base_card

_REASON_CSS = r"""
<style>
.pk-intel-reasons{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}
.pk-intel-reason{border:1px solid #203b55;background:#081522;border-radius:10px;padding:8px 9px;font-size:.56rem;line-height:1.45;font-weight:800}
.pk-intel-reason.support{border-color:#1c6449;background:#0a2a20;color:#8ce9bc}
.pk-intel-reason.concern{border-color:#76581b;background:#30270d;color:#ffe087}
.pk-intel-reason b{color:#f5fbff;font-weight:950}
.pk-intel-na{margin-top:6px;color:#7890a7;font-size:.50rem;font-weight:800}
@media(max-width:780px){.pk-intel-reasons{grid-template-columns:1fr}}
</style>
"""


def _finite(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _recent_side_rate(logs, side, line, n):
    rows = list(logs or [])[-int(n):]
    if not rows:
        return None
    wins = pushes = 0
    for row in rows:
        k = _finite(row.get("k"), None)
        if k is None:
            continue
        if side == "OVER":
            if k > line: wins += 1
            elif abs(k-line) < 1e-9: pushes += 1
        else:
            if k < line: wins += 1
            elif abs(k-line) < 1e-9: pushes += 1
    if not rows:
        return None
    return (wins + 0.5 * pushes) / len(rows)


def _h2h_values(hist):
    if not hist or not int(hist.get("games") or 0):
        return []
    text = str(hist.get("sequence") or "").replace("•", " ")
    vals = []
    for token in text.split():
        x = _finite(token, None)
        if x is not None:
            vals.append(x)
    return vals[:5]


def _h2h_rate(vals, side, line):
    vals = list(vals or [])
    if len(vals) < 2:
        return None
    wins = pushes = 0
    for k in vals:
        if side == "OVER":
            if k > line: wins += 1
            elif abs(k-line) < 1e-9: pushes += 1
        else:
            if k < line: wins += 1
            elif abs(k-line) < 1e-9: pushes += 1
    return (wins + 0.5 * pushes) / len(vals)


def _safe_signal_rows(r):
    """Return [(name, True/False/None)] using V1.0.11 thresholds, never raise."""
    g = r.get("grade") or {}
    side = str(g.get("side") or "OVER").upper()
    line = _finite(g.get("line"), 0.0)
    p = _finite(g.get("win_prob"), 0.5)
    rel = _finite(r.get("reliability"), 0.0)

    rows = [("Model", bool(p >= 0.60))]

    try:
        logs = engine._pitcher_logs(int(r.get("player_id")), 14)
    except Exception:
        logs = []
    l5 = _recent_side_rate(logs, side, line, 5)
    l10 = _recent_side_rate(logs, side, line, 10)
    rows.append(("L5", None if l5 is None else bool(l5 >= 0.60)))
    rows.append(("L10", None if l10 is None else bool(l10 >= 0.60)))

    try:
        matchup_score = v1011._directional_matchup_score(side, r.get("opp_k_rate"), r.get("opp_k_factor"))
        rows.append(("Matchup", bool(matchup_score >= 8.0)))
    except Exception:
        rows.append(("Matchup", None))

    try:
        workload_score = v1011._directional_workload_score(r, side)
        rows.append(("Workload", bool(workload_score >= 2.5 and rel >= 0.50)))
    except Exception:
        rows.append(("Workload", None))

    try:
        current_season = int(engine.season())
    except Exception:
        current_season = 2026
    try:
        hist = v109._vs_team_history(int(r.get("player_id")), str(r.get("opponent") or ""), current_season)
        vals = _h2h_values(hist)
        hr = _h2h_rate(vals, side, line)
        rows.append(("H2H", None if hr is None else bool(hr >= 0.60)))
    except Exception:
        rows.append(("H2H", None))

    return rows


def _reason_html(r):
    rows = _safe_signal_rows(r)
    supports = [name for name, state in rows if state is True]
    concerns = [name for name, state in rows if state is False]
    unavailable = [name for name, state in rows if state is None]
    e = v101._e
    support_text = " • ".join(supports) if supports else "None"
    concern_text = " • ".join(concerns) if concerns else "None"
    na_text = " • ".join(unavailable)
    na_html = f'<div class="pk-intel-na">N/A: {e(na_text)}</div>' if na_text else ""
    return dedent(f'''
    <div class="pk-intel-reasons">
      <div class="pk-intel-reason support"><b>✅ Supports:</b> {e(support_text)}</div>
      <div class="pk-intel-reason concern"><b>⚠️ Concerns:</b> {e(concern_text)}</div>
    </div>
    {na_html}
    ''').strip()


def _intelligence_with_reasons(r):
    # V1.0.11 is the last proven intelligence HTML seen in production.
    try:
        base = str(v1011._intelligence_html(r) or "").strip()
    except Exception:
        return ""
    if not base:
        return ""

    # This function itself is designed not to raise, but retain the base if anything
    # unexpected occurs so the intelligence can never disappear again.
    try:
        reasons = _reason_html(r)
    except Exception:
        return base
    if not reasons:
        return base

    marker = '<div class="pk-intel-note">'
    pos = base.find(marker)
    if pos >= 0:
        return base[:pos] + reasons + base[pos:]
    pos = base.rfind("</div>")
    if pos >= 0:
        return base[:pos] + reasons + base[pos:]
    return base + reasons


def _card(r, rank):
    html = _base_card(r, rank)
    intel = _intelligence_with_reasons(r)
    if not intel:
        return html
    pos = html.rfind("</div>")
    if pos < 0:
        return html + intel
    return html[:pos] + intel + html[pos:]


def _install():
    # Reinstall both dependencies every render. V1.0.14 owns transport; V1.0.15
    # owns only the already-ranked Top-5 card renderer.
    engine._fetch_market_lines = v1014._fetch_market_lines_multi
    v101._card = _card


_install()


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(_REASON_CSS, unsafe_allow_html=True)
    _install()
    original_markdown = st.markdown

    def _version_markdown(body, *args, **kwargs):
        if isinstance(body, str):
            for old in ("V1.0.14", "V1.0.13", "V1.0.12", "V1.0.11", "V1.0.10", "V1.0.1"):
                body = body.replace(f"Pitcher Strikeouts O/U — {old}", "Pitcher Strikeouts O/U — V1.0.15")
        return original_markdown(body, *args, **kwargs)

    st.markdown = _version_markdown
    try:
        return v1014.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.markdown = original_markdown
