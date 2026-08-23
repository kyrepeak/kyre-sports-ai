"""MLB H+R+RBI V1.0.2 — Step 1 batter/team visual identity.

Presentation-only wrapper around the verified V1.0/V1.0.1 H+R+RBI joint-event
engine. The strongest 2+ cards now mirror the MLB 1+ Hit page's Step-1 identity
layer with official MLB batter headshots and team logos.

No H/R/RBI component rate, candidate pool, lineup rule, finalist selection,
Monte Carlo simulation, threshold probability, ranking, confidence or fair-odds
math is changed.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import mlb_hrrbi_hub_v101 as prior
from engine import odds

MODEL_VERSION = "H+R+RBI V1.0.2"
base = prior.base


def _safe_id(value):
    try:
        if value is None:
            return None
        number = int(float(value))
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def mlb_player_headshot_url(player_id, width=180):
    pid = _safe_id(player_id)
    if pid is None:
        return None
    width = max(80, min(int(width), 400))
    return (
        "https://img.mlbstatic.com/mlb-photos/image/upload/"
        f"w_{width},q_auto:best,f_auto/v1/people/{pid}/headshot/67/current"
    )


def mlb_team_logo_url(team_id):
    tid = _safe_id(team_id)
    if tid is None:
        return None
    return f"https://www.mlbstatic.com/team-logos/{tid}.svg"


def _img(url, css_class, alt):
    if not url:
        return ""
    return (
        f'<img class="{css_class}" src="{escape(url, quote=True)}" '
        f'alt="{escape(str(alt or "MLB image"), quote=True)}" '
        'loading="lazy" referrerpolicy="no-referrer" '
        'onerror="this.style.display=\'none\'">'
    )


_EXTRA_CSS = r"""
<style>
.hrr-identity{display:flex;align-items:center;gap:11px;margin:9px 0 5px;min-height:76px}
.hrr-batter-photo{width:70px;height:70px;border-radius:50%;object-fit:cover;object-position:center top;background:#0a1726;border:1px solid #315a79;flex:0 0 70px}
.hrr-team-logo{width:34px;height:34px;object-fit:contain;vertical-align:middle;filter:drop-shadow(0 2px 4px rgba(0,0,0,.28));margin-right:5px}
.hrr-identity-copy{min-width:0;flex:1}.hrr-identity .hrr-name{margin-top:0}
.hrr-image-source{font-size:.49rem;color:#66849e;letter-spacing:.06em;text-transform:uppercase;margin-top:4px;font-weight:850}
.hrr-step1-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #2a6078;background:#071d2b;color:#79dfff;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr-batter-photo{width:64px;height:64px;flex-basis:64px}.hrr-team-logo{width:31px;height:31px}}
</style>
"""

if "hrr-batter-photo" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v102(r, rank, threshold):
    sim = r["sim"]
    p = base._threshold_prob(sim, threshold)
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    source = "✅ CONFIRMED" if r.get("lineup_confirmed") else "🕒 PROJECTED"
    cls = "hrr-card one" if rank == 1 else "hrr-card"
    conf_cls = "" if r.get("confidence") == "HIGH" else " med"
    l10 = (r.get("l10") or {}).get("combined_pg")
    l5 = (r.get("l5") or {}).get("combined_pg")

    player_name = r.get("player_name")
    team_name = r.get("team")
    player_img = _img(
        mlb_player_headshot_url(r.get("player_id")),
        "hrr-batter-photo",
        player_name,
    )
    team_img = _img(
        mlb_team_logo_url(r.get("team_id")),
        "hrr-team-logo",
        team_name,
    )

    identity = (
        '<div class="hrr-identity">'
        f'{player_img}'
        '<div class="hrr-identity-copy">'
        f'<div class="hrr-name">{prior._e(player_name)}</div>'
        f'<div class="hrr-meta">{team_img}{prior._e(team_name)} vs {prior._e(r.get("opponent"))}'
        f'<br>vs {prior._e(r.get("starter_name"))} • Bat #{prior._e(r.get("position"))} • {prior._e(r.get("first_pitch"))}</div>'
        '<div class="hrr-image-source">Step 1 • MLB official visual identity</div>'
        '</div></div>'
    )

    return f'''<div class="{cls}">
      <div class="hrr-rank">{medal} Rank {rank} • {source}</div>
      {identity}
      <div class="hrr-prob">{p*100:.1f}%</div><div class="hrr-prob-label">{threshold}+ H+R+RBI probability • Fair {odds(p)}</div>
      <div class="hrr-stats">
        <div class="hrr-stat"><span>xH</span><b>{sim['expected_h']:.2f}</b></div>
        <div class="hrr-stat"><span>xR</span><b>{sim['expected_r']:.2f}</b></div>
        <div class="hrr-stat"><span>xRBI</span><b>{sim['expected_rbi']:.2f}</b></div>
        <div class="hrr-stat"><span>xCombined</span><b>{sim['expected_total']:.2f}</b></div>
        <div class="hrr-stat"><span>3+</span><b>{sim['p3']*100:.1f}%</b></div>
        <div class="hrr-stat"><span>4+</span><b>{sim['p4']*100:.1f}%</b></div>
        <div class="hrr-stat"><span>L10</span><b>{prior._fmt_recent(l10)}</b></div>
        <div class="hrr-stat"><span>L5</span><b>{prior._fmt_recent(l5)}</b></div>
      </div>
      <div class="hrr-conf{conf_cls}">{prior._e(r.get('confidence'))}</div>
    </div>'''


# Presentation seam only. V1.0.1 already patches this exact renderer to be
# null-safe; V1.0.2 replaces only the card HTML while retaining the same data.
base._card = _card_v102


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr-step1-badge">🖼️ H+R+RBI V1.0.2 • Step 1 identity active</div>',
        unsafe_allow_html=True,
    )
    return prior.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
