"""MLB Pitcher Strikeouts O/U V1.0.13 — resilient Top-5 evidence reasons.

Presentation/intelligence-only repair on top of V1.0.11/V1.0.12. The existing
Top-5 ordering, projection math, Monte Carlo, sportsbook parsing, evidence score
and evidence grade are unchanged.

V1.0.13 deliberately reuses V1.0.11's proven intelligence HTML, then injects only
compact Supports / Concerns boxes. If reason construction fails, the full V1.0.11
intelligence block still renders. The Top-5 card renderer is also re-applied at
render time so Streamlit hot reload / import order cannot silently restore an
older card renderer.
"""
from __future__ import annotations

from textwrap import dedent

import streamlit as st

import mlb_pitcher_k_hub_v1011 as v1011
import mlb_pitcher_k_hub_v101 as v101

engine = v1011.engine
MODEL_VERSION = "Pitcher K V1.0.13"
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
    """Use the exact V1.0.11 evidence signal thresholds."""
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


def _reason_html(r):
    try:
        logs = engine._pitcher_logs(int(r.get("player_id")), 14)
    except Exception:
        logs = []

    try:
        current_season = int(engine.season())
    except Exception:
        current_season = 2026

    try:
        # Reuse the same cached H2H summary V1.0.11 already uses.
        hist = v1011.v109._vs_team_history(
            int(r.get("player_id")), str(r.get("opponent") or ""), current_season
        )
    except Exception:
        hist = {"games": 0, "avg_k": None, "k9": None, "sequence": "Unavailable"}

    supports, concerns = _signal_summary(r, logs, hist)
    e = v101._e
    support_text = " • ".join(supports) if supports else "None"
    concern_text = " • ".join(concerns) if concerns else "None"
    return dedent(f'''
    <div class="pk-intel-reasons">
      <div class="pk-intel-reason support"><b>✅ Supports:</b> {e(support_text)}</div>
      <div class="pk-intel-reason concern"><b>⚠️ Concerns:</b> {e(concern_text)}</div>
    </div>
    ''').strip()


def _intelligence_with_reasons(r):
    """Never lose the proven V1.0.11 intelligence if reason generation fails."""
    try:
        base = str(v1011._intelligence_html(r) or "").strip()
    except Exception:
        base = ""
    if not base:
        return ""

    try:
        reasons = _reason_html(r)
    except Exception:
        reasons = ""
    if not reasons:
        return base

    marker = '<div class="pk-intel-note">'
    pos = base.find(marker)
    if pos >= 0:
        return f"{base[:pos]}{reasons}{base[pos:]}"

    # Fallback: insert before the outer pk-intel closing div.
    pos = base.rfind("</div>")
    if pos >= 0:
        return f"{base[:pos]}{reasons}{base[pos:]}"
    return f"{base}{reasons}"


def _card_with_resilient_reasons(r, rank):
    html = _base_card(r, rank)
    intel = _intelligence_with_reasons(r)
    if not intel:
        return html
    pos = html.rfind("</div>")
    if pos < 0:
        return f"{html}{intel}"
    return f"{html[:pos]}{intel}{html[pos:]}"


def _install_card_renderer():
    # Re-apply immediately before the existing renderer runs. This guards against
    # import-order/hot-reload resets while touching only ranked Top-5 card output.
    v101._card = _card_with_resilient_reasons


_install_card_renderer()


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(_REASON_CSS, unsafe_allow_html=True)
    _install_card_renderer()

    original_markdown = st.markdown

    def _version_markdown(body, *args, **kwargs):
        if isinstance(body, str):
            body = body.replace("Pitcher Strikeouts O/U — V1.0.12", "Pitcher Strikeouts O/U — V1.0.13")
            body = body.replace("Pitcher Strikeouts O/U — V1.0.11", "Pitcher Strikeouts O/U — V1.0.13")
            body = body.replace("Pitcher Strikeouts O/U — V1.0.10", "Pitcher Strikeouts O/U — V1.0.13")
            body = body.replace("Pitcher Strikeouts O/U — V1.0.1", "Pitcher Strikeouts O/U — V1.0.13")
        return original_markdown(body, *args, **kwargs)

    st.markdown = _version_markdown
    try:
        # Delegate to the stable V1.0.11 pipeline; only the card renderer above is new.
        return v1011.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.markdown = original_markdown
