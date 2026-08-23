"""MLB Pitcher Strikeouts O/U V1.0.11 — evidence-based Top-5 Pick Strength.

Additive presentation/intelligence upgrade only. The existing Strongest Pitcher
Strikeout O/U ranking remains driven by the proven V1.0.7 model probability.
V1.0.11 changes only the Pick Strength label inside those already-ranked Top-5
cards so ELITE/STRONG/MEDIUM/LEAN/PASS reflects broader evidence agreement:
model probability, L5/L10 results at the exact line, opponent K environment,
workload/reliability and low-weight pitcher-vs-opponent history.

Projection math, sportsbook parsing, line grading, Monte Carlo, candidate pool and
Top-5 ordering are unchanged.
"""
from __future__ import annotations

import math
from textwrap import dedent

import streamlit as st

import mlb_pitcher_k_hub_v1010 as v1010
import mlb_pitcher_k_hub_v109 as v109
import mlb_pitcher_k_hub_v101 as v101

engine = v1010.engine
MODEL_VERSION = "Pitcher K V1.0.11"
_base_card = v1010._base_card


def _finite(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _clip01(value):
    return max(0.0, min(1.0, float(value)))


def _recent_rate(logs, side, line, n):
    rows = list(logs or [])[-int(n):]
    if not rows:
        return None, 0, 0
    wins = pushes = 0
    for row in rows:
        k = _finite(row.get("k"), 0.0)
        if side == "OVER":
            if k > line:
                wins += 1
            elif abs(k - line) < 1e-9:
                pushes += 1
        else:
            if k < line:
                wins += 1
            elif abs(k - line) < 1e-9:
                pushes += 1
    # Push receives half-credit for descriptive evidence only; model grading is untouched.
    rate = (wins + 0.5 * pushes) / len(rows)
    return float(rate), wins, pushes


def _h2h_values(hist):
    if not hist or not int(hist.get("games") or 0):
        return []
    text = str(hist.get("sequence") or "").replace("•", " ")
    out = []
    for token in text.split():
        value = _finite(token)
        if value is not None:
            out.append(value)
    return out[:5]


def _h2h_side_rate(values, side, line):
    vals = list(values or [])
    if not vals:
        return None
    wins = pushes = 0
    for k in vals:
        if side == "OVER":
            if k > line:
                wins += 1
            elif abs(k - line) < 1e-9:
                pushes += 1
        else:
            if k < line:
                wins += 1
            elif abs(k - line) < 1e-9:
                pushes += 1
    return float((wins + 0.5 * pushes) / len(vals))


def _directional_matchup_score(side, opp_rate, opp_factor):
    """0..15; league-average environment is intentionally near the middle."""
    rate = _finite(opp_rate, 0.225)
    factor = _finite(opp_factor, 1.0)
    rate_support_over = _clip01((rate - 0.18) / 0.09)
    factor_support_over = _clip01((factor - 0.82) / 0.38)
    over_support = 0.65 * rate_support_over + 0.35 * factor_support_over
    support = over_support if side == "OVER" else (1.0 - over_support)
    return 15.0 * _clip01(support)


def _directional_workload_score(r, side):
    """0..5; projected innings supports Overs when high and Unders when short."""
    ip = _finite(r.get("projected_ip"), 5.5)
    if side == "OVER":
        support = _clip01((ip - 4.5) / 1.8)
    else:
        support = _clip01((6.5 - ip) / 1.8)
    return 5.0 * support


def _evidence_grade(r, logs, hist):
    g = r.get("grade") or {}
    side = str(g.get("side") or "OVER").upper()
    line = _finite(g.get("line"), 0.0)
    p = _finite(g.get("win_prob"), 0.5)
    rel = _clip01(_finite(r.get("reliability"), 0.0))

    l5_rate, _, _ = _recent_rate(logs, side, line, 5)
    l10_rate, _, _ = _recent_rate(logs, side, line, 10)
    h2h_vals = _h2h_values(hist)
    h2h_rate = _h2h_side_rate(h2h_vals, side, line)

    # 35 points — independent model probability. Full credit at 80%+.
    model_score = 35.0 * _clip01((p - 0.50) / 0.30)

    # 30 points — recent actual results at this exact line.
    l5_score = 15.0 * (l5_rate if l5_rate is not None else 0.50)
    l10_score = 15.0 * (l10_rate if l10_rate is not None else 0.50)

    # 15 points — opponent strikeout environment, directional to the selected side.
    matchup_score = _directional_matchup_score(side, r.get("opp_k_rate"), r.get("opp_k_factor"))

    # 15 points — reliability (10) + side-supportive workload (5).
    reliability_score = 10.0 * rel
    workload_score = _directional_workload_score(r, side)

    # 5 points — H2H is deliberately low weight. No sample = neutral 2.5.
    if h2h_rate is None:
        h2h_score = 2.5
    else:
        sample = min(len(h2h_vals), 5)
        shrink = sample / (sample + 3.0)
        shrunk = 0.50 * (1.0 - shrink) + h2h_rate * shrink
        h2h_score = 5.0 * shrunk

    score = (
        model_score + l5_score + l10_score + matchup_score +
        reliability_score + workload_score + h2h_score
    )
    score = max(0.0, min(100.0, score))

    # Count broad agreement signals for transparency. H2H only counts with >=2 meetings.
    signals = [("Model", p >= 0.60)]
    if l5_rate is not None:
        signals.append(("L5", l5_rate >= 0.60))
    if l10_rate is not None:
        signals.append(("L10", l10_rate >= 0.60))
    signals.append(("Matchup", matchup_score >= 8.0))
    signals.append(("Workload", workload_score >= 2.5 and rel >= 0.50))
    if len(h2h_vals) >= 2 and h2h_rate is not None:
        signals.append(("H2H", h2h_rate >= 0.60))
    supportive = sum(1 for _, ok in signals if ok)
    total_signals = len(signals)

    # ELITE requires broad agreement, not just a huge model number.
    if (
        score >= 82.0 and p >= 0.68 and rel >= 0.55 and
        (l10_rate is None or l10_rate >= 0.60) and
        (l5_rate is None or l5_rate >= 0.60) and
        supportive >= max(4, total_signals - 1)
    ):
        grade, css = "ELITE", "elite"
    elif score >= 70.0 and p >= 0.62 and rel >= 0.48 and supportive >= 3:
        grade, css = "STRONG", "strong"
    elif score >= 58.0 and p >= 0.56:
        grade, css = "MEDIUM", "medium"
    elif score >= 50.0 and p >= 0.53:
        grade, css = "LEAN", "hard"
    else:
        grade, css = "PASS", "hard"

    return {
        "grade": grade,
        "css": css,
        "score": score,
        "supportive": supportive,
        "signals": total_signals,
    }


def _intelligence_html(r):
    g = r.get("grade") or {}
    side = str(g.get("side") or "OVER").upper()
    line = _finite(g.get("line"), 0.0)
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
        hist = v109._vs_team_history(int(r.get("player_id")), str(r.get("opponent") or ""), current_season)
    except Exception:
        hist = {"games": 0, "avg_k": None, "k9": None, "sequence": "Unavailable"}

    evidence = _evidence_grade(r, logs, hist)
    matchup, matchup_cls = v109._matchup_grade(r)
    workload = v109._workload_grade(r)
    opp_k = _finite(r.get("opp_k_rate"))
    hist_avg = hist.get("avg_k")
    hist_k9 = hist.get("k9")
    hist_text = (
        f"{hist_avg:.1f} K avg • {hist_k9:.1f} K/9"
        if hist.get("games") and hist_avg is not None and hist_k9 is not None
        else "No recent sample"
    )
    hist_seq = hist.get("sequence") or "—"
    rel = _finite(r.get("reliability"), 0.0)
    e = v101._e

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
      <div class="pk-intel-note">Evidence agreement {evidence['supportive']}/{evidence['signals']} signals • H2H is low-weight and shrunk toward neutral for small samples • Reliability {rel*100:.0f}% • Top-5 ranking/model probability remains unchanged.</div>
    </div>
    ''').strip()


def _card_with_evidence_strength(r, rank):
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


# Patch only the renderer used for the already-ranked Top-5 cards.
v101._card = _card_with_evidence_strength


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    # Reuse V1.0.9 card-intelligence CSS and the V1.0.10 clean HTML path.
    original_markdown = st.markdown

    def _version_markdown(body, *args, **kwargs):
        if isinstance(body, str):
            body = body.replace("Pitcher Strikeouts O/U — V1.0.10", "Pitcher Strikeouts O/U — V1.0.11")
            body = body.replace("Pitcher Strikeouts O/U — V1.0.9", "Pitcher Strikeouts O/U — V1.0.11")
            body = body.replace("Pitcher Strikeouts O/U — V1.0.1", "Pitcher Strikeouts O/U — V1.0.11")
        return original_markdown(body, *args, **kwargs)

    st.markdown = _version_markdown
    try:
        return v1010.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.markdown = original_markdown
