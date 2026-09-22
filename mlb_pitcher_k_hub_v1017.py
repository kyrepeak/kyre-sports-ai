"""MLB Pitcher Strikeouts O/U V1.0.17 — Top-5 MLB player headshots.

Additive presentation-only upgrade on top of the frozen/verified V1.0.16
Pitcher-K checkpoint. V1.0.17 adds MLB player headshots only to the already-ranked
Top-5 Strongest Pitcher Strikeout O/U cards.

Preserved unchanged:
- V1.0.14 SportsGameOdds primary + Odds-API.io fallback/gap-fill + same-slate cache
- V1.0.15 Supports / Concerns intelligence
- V1.0.16 renderer-order repair
- projection math, Monte Carlo, sportsbook line grading, Evidence Score,
  candidate pool, Pick Strength and Top-5 probability ordering

Headshots use the existing MLB player_id already present in each projected pitcher
row. Images load directly in the browser from MLB's image CDN; no additional
server-side image requests are added. A local inline silhouette is used on image
failure so a missing portrait can never break or hide a Top-5 card.
"""
from __future__ import annotations

import re
from urllib.parse import quote

import streamlit as st

import mlb_pitcher_k_hub_v1016 as v1016
import mlb_pitcher_k_hub_v1015 as v1015
import mlb_pitcher_k_hub_v1014 as v1014
import mlb_pitcher_k_hub_v101 as v101

engine = v1016.engine
MODEL_VERSION = "Pitcher K V1.0.17"

_HEADSHOT_CSS = r"""
<style>
.pk-player-headshot{
    width:58px;height:58px;flex:0 0 58px;border-radius:50%;object-fit:cover;
    object-position:center top;background:#091724;border:2px solid #2c4f69;
    box-shadow:0 3px 14px rgba(0,0,0,.24);display:block;
}
.pk-player-row{align-items:center!important;gap:10px!important;min-height:60px!important}
@media(max-width:640px){
    .pk-player-headshot{width:52px;height:52px;flex-basis:52px}
    .pk-player-row{gap:8px!important;min-height:54px!important}
}
</style>
"""


def _fallback_headshot_uri() -> str:
    svg = """<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>
    <rect width='96' height='96' rx='48' fill='#0d1b2a'/>
    <circle cx='48' cy='34' r='18' fill='#71859b'/>
    <path d='M18 84c5-19 21-28 30-28s25 9 30 28' fill='#71859b'/>
    </svg>"""
    return "data:image/svg+xml;charset=UTF-8," + quote(svg)


FALLBACK_HEADSHOT = _fallback_headshot_uri()


def _headshot_url(player_id) -> str:
    try:
        pid = int(player_id)
    except Exception:
        return FALLBACK_HEADSHOT
    if pid <= 0:
        return FALLBACK_HEADSHOT
    # MLB's public player-photo CDN. Width is intentionally modest for Top-5 cards.
    return (
        "https://img.mlbstatic.com/mlb-photos/image/upload/"
        f"w_180,q_100/v1/people/{pid}/headshot/67/current"
    )


def _headshot_img(r) -> str:
    url = _headshot_url(r.get("player_id"))
    name = v101._e(r.get("player_name") or "MLB pitcher")
    fallback = FALLBACK_HEADSHOT
    return (
        f'<img class="pk-player-headshot" src="{url}" alt="{name} headshot" '
        f'loading="lazy" decoding="async" '
        f'onerror="this.onerror=null;this.src=\'{fallback}\';">'
    )


def _card_with_headshot(r, rank):
    """Reuse the verified V1.0.15 full intelligence card and add one image only."""
    html = v1015._card(r, rank)
    if not isinstance(html, str) or not html:
        return html

    img = _headshot_img(r)

    # The verified logo card already owns a flex player row. Insert the headshot
    # at the beginning of that row so the existing team logo + name remain intact.
    pattern = r'(<div class="pk-player-row"[^>]*>)'
    if re.search(pattern, html):
        return re.sub(pattern, lambda m: m.group(1) + img, html, count=1)

    # Defensive fallback for any future card markup change: wrap only the name,
    # never touch the stats/intelligence/market portions of the card.
    name = v101._e(r.get("player_name"))
    old = f'<div class="pk-name">{name}</div>'
    if old in html:
        new = f'<div class="pk-player-row">{img}{old}</div>'
        return html.replace(old, new, 1)
    return html


def _install_v1017():
    """Preserve V1.0.14 transport while making the final draw owner V1.0.17."""
    engine._fetch_market_lines = v1014._fetch_market_lines_multi
    v101._card = _card_with_headshot


_install_v1017()


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(_HEADSHOT_CSS, unsafe_allow_html=True)

    # V1.0.16 owns the verified renderer-order repair. Temporarily replace its
    # final installer so every place that would install V1.0.15 now installs our
    # V1.0.17 headshot wrapper instead. This avoids reopening the V1.0.13 collision.
    original_installer = v1016._install_final_renderer
    v1016._install_final_renderer = _install_v1017
    _install_v1017()

    original_markdown = st.markdown

    def _version_markdown(body, *args, **kwargs):
        if isinstance(body, str):
            body = body.replace(
                "Pitcher Strikeouts O/U — V1.0.16",
                "Pitcher Strikeouts O/U — V1.0.17",
            )
        return original_markdown(body, *args, **kwargs)

    st.markdown = _version_markdown
    try:
        return v1016.render_pitcher_k_hub(
            games_df, section_header, status_info, team_logo, h
        )
    finally:
        st.markdown = original_markdown
        v1016._install_final_renderer = original_installer
        # Leave the current interpreter in the desired Pitcher-K-only state.
        _install_v1017()
