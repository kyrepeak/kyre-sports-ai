"""MLB Pitcher Strikeouts O/U V1.0.12 — Top-5 evidence reasons.

Presentation/intelligence-only upgrade on top of V1.0.11. The existing Top-5
ordering, projection math, Monte Carlo, sportsbook parsing and evidence score are
unchanged. V1.0.12 adds compact Supports / Concerns labels inside each already-
ranked Top-5 card using the exact same signal thresholds as the V1.0.11 evidence
grade.
"""
from __future__ import annotations

from textwrap import dedent

import streamlit as st

import mlb_pitcher_k_hub_v1011 as v1011
import mlb_pitcher_k_hub_v109 as v109
import mlb_pitcher_k_hub_v101 as v101

engine = v1011.engine
MODEL_VERSION = "Pitcher K V1.0.12"
_base_card = v1011._base_card

_REASON_CSS = r"""
<style>
.pk-intel-reasons{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}
.pk-intel-reason{border:1px solid #203b55;background:#081522;border-radius:10px;padding:8px 9px;font-size:.56rem;line-height:1.45;font-weight:800}
.pk-intel-reason.support{border-color:#1c6449;background:#0a2a20;color:#8ce9bc}
.pk-intel-reason.concern{border-color:#76581b;background:#30270d;color:#ffe087}
.pk-intel-reason b{color:#f5fbff;font-weight:950}
@media(max-width:780px){.pk-intel-reasons{grid-template-columns:1fr}}
</style>
"""


def _signal_summary(r, logs, hist):
    """Return support/concern labels using V1.0.11's exact signal thresholds."""
    g = r.get("grade") or {}
    side = str(g.get("side") or "OVER").upper()
    line = v1011._finite(g.get("line"), 0.0)
    p = v1011._finite(g.get("win_prob"), 0.5)
    rel = v1011._clip01(v1011._finite(r.get("reliability"), 0.0))

    l5_rate, _, _ = v1011._recent_rate(logs, side, line, 5)
    l10_rate, _, _ = v1011._recent_rate(logs, side, line, 10)
    h2h_vals = v1011._h2h_values(hist)
    h2h_rate = v1011._h2h_side_rate(h2h_vals, side, line)
    matchup_score = v1011._directional_matchup_score(
        side, r.get("opp_k_rate"), r.get("opp_k_factor")
    )
    workload_score = v1011._directional_workload_score(r, side)

    signals = [("Model", p >= 0.60)]
    if l5_rate is not None:
        signals.append(("L5", l5_rate >= 0.60))
    if l10_rate is not None:
        signals.append(("L10", l10_rate >= 0.60))
    signals.append(("Matchup", matchup_score >= 8.0))
    signals.append(("Workload", workload_score >= 2.5 and rel >= 0.50))
    if len(h2h_vals) >= 2 and h2h_rate is not None:
        signals.append(("H2H", h2h_rate >= 0.60))

    supports = [name for name, ok in signals if ok]
    concerns = [name for name, ok in signals if not ok]
    return supports, concerns


def _intelligence_html(r):
    g = r.get("grade") or {}
    side = str(g.get("side") or "OVER").upper()
    line = v1011._finite(g.get("line"), 0.0)
    try:
        logs = engine._pitcher_logs(int(r.get("player_id")), 14)
    except Exception:
        logs = []

    l5_text = v109._hit_count(logs, side, line, 5)
    l10_text = v109._hit_count(logs, side, line, 10)
    seq = v109._k_sequence(logs, 5)

    try:
        current_season = int(engine.season())
    except Exception:
        current_season = 2026
    try:
        hist = v109._vs_team_history(
            int(r.get("player_id")), str(r.get("opponent") or ""), current_season
        )
    except Exception:
        hist = {"games": 0, "avg_k": None, "k9": None, "sequence": "Unavailable"}

    evidence = v1011._evidence_grade(r, logs, hist)
    supports, concerns = _signal_summary(r, logs, hist)
    matchup, matchup_cls = v109._matchup_grade(r)
    workload = v109._workload_grade(r)
    opp_k = v1011._finite(r.get("opp_k_rate"))
    hist_avg = hist.get("avg_k")
    hist_k9 = hist.get("k9")
    hist_text = (
        f"{hist_avg:.1f} K avg • {hist_k9:.1f} K/9"
        if hist.get("games") and hist_avg is not None and hist_k9 is not None
        else "No recent sample"
    )
    hist_seq = hist.get("sequence") or "—"
    rel = v1011._finite(r.get("reliability"), 0.0)
    e = v101._e

    support_text = " • ".join(supports) if supports else "None"
    concern_text = " • ".join(concerns) if concerns else "None"

    return dedent(f'''
    <div class="pk-intel">
      <div class="pk-intel-badges">
        <span class="pk-intel-badge {evidence['css']}">PICK STRENGTH • {e(evidence['grade'])}</span>
        <span class="pk-intel-badge {matchup_cls}">MATCHUP • {e(matchup)}</span>
        <span class="pk-intel-badge">WORKLOAD • {e(workload)}</span>
        <span class="pk-intel-badge">EVIDENCE • {e(round(evidence['score']))}/100</span>
      </div>
      <div class="pk-intel-grid">
        <div class="pk-intel-stat"><span>Last 5 Ks</span><b>{e(seq)}</b></div>
        <div class="pk-intel-stat"><span>L5 vs {e(side)} {line:g}</span><b>{e(l5_text)}</b></div>
        <div class="pk-intel-stat"><span>L10 vs {e(side)} {line:g}</span><b>{e(l10_text)}</b></div>
        <div class="pk-intel-stat"><span>Vs {e(r.get('opponent'))}</span><b>{e(hist_text)}</b></div>
        <div class="pk-intel-stat"><span>Recent H2H Ks</span><b>{e(hist_seq)}</b></div>
        <div class="pk-intel-stat"><span>Opponent K environment</span><b>{f'{opp_k*100:.1f}%' if opp_k is not None else '—'}</b></div>
      </div>
      <div class="pk-intel-reasons">
        <div class="pk-intel-reason support"><b>✅ Supports:</b> {e(support_text)}</div>
        <div class="pk-intel-reason concern"><b>⚠️ Concerns:</b> {e(concern_text)}</div>
      </div>
      <div class="pk-intel-note">Evidence agreement {evidence['supportive']}/{evidence['signals']} signals • Supports/Concerns use those exact same thresholds • H2H stays low-weight and shrunk toward neutral for small samples • Reliability {rel*100:.0f}% • Top-5 ranking/model probability remains unchanged.</div>
    </div>
    ''').strip()


def _card_with_reason_summary(r, rank):
    html = _base_card(r, rank)
    try:
        intel = _intelligence_html(r)
    except Exception:
        intel = ""
    if not intel:
        return html
    pos = html.rfind("</div>")
    if pos < 0:
        return f"{html}{intel}"
    return f"{html[:pos]}{intel}{html[pos:]}"


# Patch only the renderer used by the existing ranked/graded Top-5 cards.
v101._card = _card_with_reason_summary


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(_REASON_CSS, unsafe_allow_html=True)
    original_markdown = st.markdown

    def _version_markdown(body, *args, **kwargs):
        if isinstance(body, str):
            body = body.replace("Pitcher Strikeouts O/U — V1.0.11", "Pitcher Strikeouts O/U — V1.0.12")
            body = body.replace("Pitcher Strikeouts O/U — V1.0.10", "Pitcher Strikeouts O/U — V1.0.12")
            body = body.replace("Pitcher Strikeouts O/U — V1.0.1", "Pitcher Strikeouts O/U — V1.0.12")
        return original_markdown(body, *args, **kwargs)

    st.markdown = _version_markdown
    try:
        return v1011.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.markdown = original_markdown
