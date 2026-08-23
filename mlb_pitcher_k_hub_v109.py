"""MLB Pitcher Strikeouts O/U V1.0.9 — Top-5 card intelligence only.

This replaces the temporary page-level Step-1 presentation with additive detail
inside the existing Strongest Pitcher Strikeout O/U Top-5 cards only. Ranking,
projection math, workload model, opponent-K model, sportsbook parsing, line
grading and Monte Carlo remain V1.0.7 unchanged.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import math

import numpy as np
import requests
import streamlit as st

import mlb_pitcher_k_hub_v107 as v107
import mlb_pitcher_k_hub_v101 as v101

engine = v107.engine
MODEL_VERSION = "Pitcher K V1.0.9"
_base_card = v101._card

_CARD_CSS = r"""
<style>
.pk-intel{margin-top:12px;border-top:1px solid #203b55;padding-top:11px}
.pk-intel-badges{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:9px}
.pk-intel-badge{border:1px solid #31536b;background:#091827;color:#c9d9e7;border-radius:999px;padding:5px 8px;font-size:.54rem;font-weight:950;letter-spacing:.04em}
.pk-intel-badge.elite{border-color:#6d4bc4;background:#211642;color:#d8c8ff}
.pk-intel-badge.strong{border-color:#1f7a55;background:#0b3325;color:#88efbc}
.pk-intel-badge.medium{border-color:#806317;background:#3a2e0c;color:#ffe17a}
.pk-intel-badge.hard{border-color:#7a3030;background:#351313;color:#ffaaaa}
.pk-intel-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
.pk-intel-stat{border:1px solid #203b55;background:#081522;border-radius:10px;padding:8px;min-width:0}
.pk-intel-stat span{display:block;color:#718ba3;font-size:.47rem;text-transform:uppercase;font-weight:900}
.pk-intel-stat b{display:block;color:#f6f9fd;font-size:.76rem;margin-top:3px;line-height:1.25;overflow-wrap:anywhere}
.pk-intel-note{margin-top:8px;color:#8da1b8;font-size:.58rem;line-height:1.45}
@media(max-width:780px){.pk-intel-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _finite(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _hit_count(logs, side, line, n):
    rows = list(logs or [])[-int(n):]
    if not rows:
        return "—"
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
    suffix = f" • {pushes}P" if pushes else ""
    return f"{wins}/{len(rows)}{suffix}"


def _k_sequence(logs, n=5):
    rows = list(logs or [])[-int(n):]
    if not rows:
        return "—"
    vals = [str(int(round(_finite(x.get("k"), 0.0)))) for x in rows]
    return " • ".join(vals)


def _matchup_grade(r):
    rate = _finite(r.get("opp_k_rate"), .225)
    factor = _finite(r.get("opp_k_factor"), 1.0)
    if rate >= .255 or factor >= 1.12:
        return "ELITE", "elite"
    if rate >= .235 or factor >= 1.05:
        return "STRONG", "strong"
    if rate >= .215 and factor >= .94:
        return "MEDIUM", "medium"
    return "HARD", "hard"


def _pick_strength(r):
    g = r.get("grade") or {}
    p = _finite(g.get("win_prob"), .5)
    rel = _finite(r.get("reliability"), .0)
    confidence = str(r.get("confidence") or "").upper()
    if p >= .72 and rel >= .60 and confidence != "LOW":
        return "ELITE", "elite"
    if p >= .64 and rel >= .50 and confidence != "LOW":
        return "STRONG", "strong"
    if p >= .57:
        return "MEDIUM", "medium"
    return "LEAN", "hard"


def _workload_grade(r):
    ip = _finite(r.get("projected_ip"), 0.0)
    rel = _finite(r.get("reliability"), 0.0)
    if ip >= 6.0 and rel >= .62:
        return "STRONG"
    if ip >= 5.2 and rel >= .45:
        return "NORMAL"
    return "LIMITED"


def _normalize_team(name):
    return engine._norm_name(name)


@st.cache_data(ttl=900, show_spinner=False)
def _vs_team_history(player_id, opponent_name, current_season):
    """Recent completed pitching appearances versus this opponent, last 3 seasons."""
    pid = int(player_id)
    target = _normalize_team(opponent_name)
    seasons = [int(current_season) - i for i in range(3)]

    def load_year(yr):
        try:
            resp = requests.get(
                f"{engine.MLB_API}/people/{pid}/stats",
                params={"stats": "gameLog", "group": "pitching", "season": int(yr)},
                timeout=8,
            )
            resp.raise_for_status()
            groups = resp.json().get("stats") or []
            splits = groups[0].get("splits", []) if groups else []
            out = []
            for sp in splits:
                opp = ((sp.get("opponent") or {}).get("name") or "")
                if target and _normalize_team(opp) != target:
                    continue
                stat = sp.get("stat") or {}
                ip = engine.ipfloat(stat.get("inningsPitched", "0.0"))
                if ip < 1.0:
                    continue
                out.append({
                    "date": str(sp.get("date") or ""),
                    "k": _finite(stat.get("strikeOuts"), 0.0),
                    "ip": ip,
                })
            return out
        except Exception:
            return []

    rows = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = [pool.submit(load_year, yr) for yr in seasons]
        for fut in as_completed(futs):
            rows.extend(fut.result() or [])
    rows.sort(key=lambda x: x.get("date") or "", reverse=True)
    rows = rows[:5]
    if not rows:
        return {"games": 0, "avg_k": None, "avg_ip": None, "k9": None, "sequence": "No recent meetings"}
    ks = [float(x.get("k") or 0) for x in rows]
    ips = [float(x.get("ip") or 0) for x in rows]
    total_ip = sum(ips)
    return {
        "games": len(rows),
        "avg_k": float(np.mean(ks)),
        "avg_ip": float(np.mean(ips)),
        "k9": (sum(ks) * 9.0 / total_ip) if total_ip > 0 else None,
        "sequence": " • ".join(str(int(round(x))) for x in ks),
    }


def _intelligence_html(r):
    g = r.get("grade") or {}
    line = _finite(g.get("line"), 0.0)
    side = str(g.get("side") or "OVER").upper()
    try:
        logs = engine._pitcher_logs(int(r.get("player_id")), 14)
    except Exception:
        logs = []

    l5_hit = _hit_count(logs, side, line, 5)
    l10_hit = _hit_count(logs, side, line, 10)
    seq = _k_sequence(logs, 5)

    try:
        current_season = int(engine.season())
    except Exception:
        current_season = 2026
    try:
        hist = _vs_team_history(int(r.get("player_id")), str(r.get("opponent") or ""), current_season)
    except Exception:
        hist = {"games": 0, "avg_k": None, "k9": None, "sequence": "Unavailable"}

    matchup, matchup_cls = _matchup_grade(r)
    strength, strength_cls = _pick_strength(r)
    workload = _workload_grade(r)
    opp_k = _finite(r.get("opp_k_rate"))
    hist_avg = hist.get("avg_k")
    hist_k9 = hist.get("k9")
    hist_text = (
        f"{hist_avg:.1f} K avg • {hist_k9:.1f} K/9" if hist.get("games") and hist_avg is not None and hist_k9 is not None
        else "No recent sample"
    )
    hist_seq = hist.get("sequence") or "—"
    rel = _finite(r.get("reliability"), 0.0)

    e = v101._e
    return f'''
      <div class="pk-intel">
        <div class="pk-intel-badges">
          <span class="pk-intel-badge {strength_cls}">PICK STRENGTH • {e(strength)}</span>
          <span class="pk-intel-badge {matchup_cls}">MATCHUP • {e(matchup)}</span>
          <span class="pk-intel-badge">WORKLOAD • {e(workload)}</span>
        </div>
        <div class="pk-intel-grid">
          <div class="pk-intel-stat"><span>Last 5 Ks</span><b>{e(seq)}</b></div>
          <div class="pk-intel-stat"><span>L5 vs {e(side)} {line:g}</span><b>{e(l5_hit)}</b></div>
          <div class="pk-intel-stat"><span>L10 vs {e(side)} {line:g}</span><b>{e(l10_hit)}</b></div>
          <div class="pk-intel-stat"><span>Vs {e(r.get('opponent'))}</span><b>{e(hist_text)}</b></div>
          <div class="pk-intel-stat"><span>Recent H2H Ks</span><b>{e(hist_seq)}</b></div>
          <div class="pk-intel-stat"><span>Opponent K environment</span><b>{f'{opp_k*100:.1f}%' if opp_k is not None else '—'}</b></div>
        </div>
        <div class="pk-intel-note">H2H uses completed pitching appearances versus the current opponent from the current and prior two MLB seasons; small samples are descriptive only. Reliability {rel*100:.0f}% • existing model/ranking remains unchanged.</div>
      </div>'''


def _card_with_top5_intelligence(r, rank):
    html = _base_card(r, rank)
    try:
        intel = _intelligence_html(r)
    except Exception:
        intel = ""
    if not intel:
        return html
    parts = html.rsplit("</div>", 1)
    if len(parts) != 2:
        return html + intel
    return parts[0] + intel + "</div>" + parts[1]


# The existing renderer only calls _card for ranked/graded Top-5 results. Patching
# this exact symbol means the extra research is fetched only for those five cards.
v101._card = _card_with_top5_intelligence


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    original_markdown = st.markdown

    def _version_markdown(body, *args, **kwargs):
        text = str(body or "")
        if "Pitcher Strikeouts O/U" in text:
            text = text.replace("Pitcher Strikeouts O/U — V1.0.1", "Pitcher Strikeouts O/U — V1.0.9")
        return original_markdown(text if isinstance(body, str) else body, *args, **kwargs)

    st.markdown = _version_markdown
    try:
        return v107.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.markdown = original_markdown
