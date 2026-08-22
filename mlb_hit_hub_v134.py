"""MLB 1+ Hit UI V13.4 — Step 1 Top-5 visual identity repair.

Presentation-only wrapper around V13.3. The V13.3 full-slate candidate pool,
confirmed/projected lineup handling, V13 probability model, Monte Carlo,
confidence grading, ranking, calibration and persistence are unchanged.

This layer adds batter headshots and team logos to the existing V13.3 Top-5 cards
using the player_id/team_id already carried by each modeled result.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import mlb_hit_hub_v133 as base

UI_VERSION = "V13.4"


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
.hit134-identity{display:grid;grid-template-columns:72px minmax(0,1fr) 38px;align-items:center;gap:10px;margin:9px 0 5px;min-height:74px}
.hit134-photo{width:72px;height:72px;border-radius:50%;object-fit:cover;object-position:center top;background:#091827;border:1px solid #315a79;box-shadow:0 5px 14px rgba(0,0,0,.22)}
.hit134-team-logo{width:36px;height:36px;object-fit:contain;filter:drop-shadow(0 2px 4px rgba(0,0,0,.30));justify-self:end}
.hit134-copy{min-width:0}.hit134-copy .hit-pick-name{margin-top:0}.hit134-copy .hit-pick-meta{min-height:0}
.hit134-source{font-size:.48rem;color:#66849e;letter-spacing:.05em;text-transform:uppercase;margin-top:3px}
@media(max-width:700px){.hit134-identity{grid-template-columns:64px minmax(0,1fr) 32px;gap:9px}.hit134-photo{width:64px;height:64px}.hit134-team-logo{width:31px;height:31px}}
</style>
"""

if "hit134-identity" not in base.base.HIT_CSS:
    base.base.HIT_CSS = base.base.HIT_CSS + _EXTRA_CSS


def _pick_html_v134(result, rank):
    sim = result["sim"]
    cls = "hit-pick rank1" if rank == 1 else "hit-pick"
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    source = "✅ CONFIRMED" if result.get("lineup_confirmed") else "🕒 PROJECTED"
    player_name = result.get("player_name")
    team_name = result.get("team")
    player_img = _img(
        mlb_player_headshot_url(result.get("player_id")),
        "hit134-photo",
        player_name,
    )
    team_img = _img(
        mlb_team_logo_url(result.get("team_id")),
        "hit134-team-logo",
        team_name,
    )
    identity = (
        '<div class="hit134-identity">'
        f'{player_img}'
        '<div class="hit134-copy">'
        f'<div class="hit-pick-name">{base.base._e(player_name)}</div>'
        f'<div class="hit-pick-meta">{base.base._e(team_name)} vs {base.base._e(result.get("opponent"))}<br>'
        f'vs {base.base._e(result.get("starter_name"))} • Bat #{base.base._e(result.get("position"))} • {base.base._e(result.get("first_pitch"))}</div>'
        '<div class="hit134-source">MLB player + team identity</div>'
        '</div>'
        f'{team_img}'
        '</div>'
    )
    return (
        f'<div class="{cls}">'
        f'<div class="hit-rank">{medal} Rank {rank} • {source}</div>'
        f'{identity}'
        f'<div class="hit-pick-prob">{sim["p_one_plus"]*100:.1f}%</div>'
        f'<div class="hit-pick-sub">2+ {sim["p_two_plus"]*100:.1f}% • xH {sim["expected_hits"]:.2f}<br>'
        f'90% {sim["scenario_low"]*100:.1f}–{sim["scenario_high"]*100:.1f}% • Data {int(result.get("data_score",0) or 0)}/8</div>'
        f'<div class="hit-conf">{base.base._e(result.get("confidence","—"))}</div>'
        '</div>'
    )


# V13.3's scanner resolves this module-global function at render time. Replacing
# only that function leaves candidate construction, simulation, sorting and saves
# exactly as V13.3 implemented them.
base._pick_html = _pick_html_v134


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🖼️ Hit UI V13.4 • Step 1 Top-5 batter photos + team logos ACTIVE • "
        "presentation only • Hit Model V13 unchanged"
    )
    return base.render_hit_hub(games_df, section_header, status_info, team_logo, h)
