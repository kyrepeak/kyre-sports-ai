"""V20.9.1 hotfix — prevent recursion in V20.9 freshness card rendering.

V20.9 temporarily patches slate_hub_v208._edge_card_v208 with its freshness-aware
renderer. The original V20.9 no-market branch called that patched symbol again,
which recursively called itself when a game had no compatible market. This
wrapper replaces only that branch while preserving every V20.9 freshness,
no-vig, stale-filtering and slate-summary feature.
"""

import slate_hub_v209 as base209

MODEL_VERSION = "V20.9.1"

_ORIGINAL_EDGE_V209 = base209._edge_card_v209


def _edge_card_v2091(title, item):
    if not item:
        return (
            '<div class="sl-edge pass"><div class="sl-edge-top">'
            f'<span class="sl-edge-market">{base209.escape(title)}</span>'
            '<span class="sl-edge-grade">NO MARKET</span></div>'
            '<div class="sl-edge-pick">Waiting for matching line</div>'
            '<div class="sl-edge-detail">A calibrated comparison appears when the model and a compatible two-way sportsbook market are both available.</div>'
            '</div>'
        )
    return _ORIGINAL_EDGE_V209(title, item)


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    old_edge = base209._edge_card_v209
    old_version = base209.MODEL_VERSION
    base209._edge_card_v209 = _edge_card_v2091
    base209.MODEL_VERSION = MODEL_VERSION
    try:
        return base209.render_slate_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        base209._edge_card_v209 = old_edge
        base209.MODEL_VERSION = old_version
