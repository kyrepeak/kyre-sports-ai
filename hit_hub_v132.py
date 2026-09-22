"""MLB 1+ Hit UI V13.2 — Step 1 batter/team visual identity layer.

This wrapper preserves Hit Model V13 and the complete V13.1 workflow. It changes
presentation only: Top-5 cards receive official MLB batter headshots and team
logos resolved from the player_id/team_id already present in the verified slate
payload. No projection input, ranking, Monte Carlo, lineup rule, calibration,
history write, or sportsbook behavior is changed.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import hit_hub_v131 as base

UI_VERSION = "V13.2"


def _safe_id(value):
    """Return a positive integer identifier or None without making a network call."""
    try:
        if value is None:
            return None
        number = int(float(value))
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def mlb_player_headshot_url(player_id, width=180):
    """Official MLB image-CDN headshot URL for an MLBAM player id."""
    pid = _safe_id(player_id)
    if pid is None:
        return None
    width = max(80, min(int(width), 400))
    return (
        "https://img.mlbstatic.com/mlb-photos/image/upload/"
        f"w_{width},q_auto:best,f_auto/v1/people/{pid}/headshot/67/current"
    )


def mlb_team_logo_url(team_id):
    """Official MLB static team-logo URL for an MLB team id."""
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
.hit-pick-identity{display:flex;align-items:center;gap:10px;margin:8px 0 4px;min-height:72px}
.hit-batter-photo{width:68px;height:68px;border-radius:50%;object-fit:cover;object-position:center top;background:#0a1726;border:1px solid #315a79;flex:0 0 68px}
.hit-team-logo{width:34px;height:34px;object-fit:contain;filter:drop-shadow(0 2px 4px rgba(0,0,0,.28));flex:0 0 34px}
.hit-pick-identity-copy{min-width:0;flex:1}
.hit-image-source{font-size:.50rem;color:#66849e;letter-spacing:.05em;text-transform:uppercase;margin-top:3px}
@media(max-width:700px){.hit-batter-photo{width:62px;height:62px;flex-basis:62px}.hit-team-logo{width:31px;height:31px;flex-basis:31px}}
</style>
"""

# V13.1 injects HIT_CSS once during render. Appending presentation CSS keeps the
# source UI intact while adding only the visual identity layer.
if "hit-pick-identity" not in base.HIT_CSS:
    base.HIT_CSS = base.HIT_CSS + _EXTRA_CSS


_ORIGINAL_HERO = base._hero


def _hero_v132():
    _ORIGINAL_HERO()
    st.caption(
        "🖼️ Hit UI V13.2 • Step 1 batter/team image resolver ACTIVE • "
        "official MLB headshots + team logos • presentation only • model V13 unchanged"
    )


def _top_pick_html_v132(result, rank):
    sim = result["sim"]
    cls = "hit-pick rank1" if rank == 1 else "hit-pick"
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    player_name = result.get("player_name")
    team_name = result.get("team")
    player_img = _img(
        mlb_player_headshot_url(result.get("player_id")),
        "hit-batter-photo",
        player_name,
    )
    team_img = _img(
        mlb_team_logo_url(result.get("team_id")),
        "hit-team-logo",
        team_name,
    )
    identity = (
        '<div class="hit-pick-identity">'
        f'{player_img}'
        '<div class="hit-pick-identity-copy">'
        f'<div class="hit-pick-name">{base._e(player_name)}</div>'
        f'<div class="hit-pick-meta">{team_img} {base._e(team_name)} vs {base._e(result.get("opponent"))}'
        f'<br>vs {base._e(result.get("starter_name"))} • Bat #{base._e(result.get("position"))}</div>'
        '<div class="hit-image-source">MLB official visual identity</div>'
        '</div></div>'
    )
    return (
        f'<div class="{cls}">'
        f'<div class="hit-rank">{medal} Rank {rank} • ✅ CONFIRMED</div>'
        f'{identity}'
        f'<div class="hit-pick-prob">{sim["p_one_plus"]*100:.1f}%</div>'
        f'<div class="hit-pick-sub">2+ {sim["p_two_plus"]*100:.1f}% • xH {sim["expected_hits"]:.2f}'
        f'<br>90% {sim["scenario_low"]*100:.1f}–{sim["scenario_high"]*100:.1f}% • Data {int(result.get("data_score",0) or 0)}/8</div>'
        f'<div class="hit-conf">{base._e(result.get("confidence","—"))}</div>'
        '</div>'
    )


# Patch only V13.1 presentation helpers. Scanner/model functions remain the exact
# same objects imported by the frozen source module.
base._hero = _hero_v132
base._top_pick_html = _top_pick_html_v132


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    return base.render_hit_hub(games_df, section_header, status_info, team_logo, h)
