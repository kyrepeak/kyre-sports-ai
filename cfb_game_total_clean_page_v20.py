"""CFB Game Total clean page V20 — page cleanup Step 1 data contract.

Additive successor to V19. V20 changes only the selected Game Total slate data
owner so the page can use the normalized field-level fallback in Slate V2.
V19 Step 6 visuals/data and all frozen Step-11/Step-12 math remain unchanged.
"""
from __future__ import annotations

from html import escape
from threading import RLock
from typing import Any, Mapping

import cfb_game_total_clean_page_v9 as compact_owner
import cfb_game_total_clean_page_v19 as prior
import cfb_game_total_slate_v2 as slate_v2

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V20 • PAGE CLEANUP STEP 1 DATA"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v19"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE CLEANUP STEP 1 DATA ACTIVE"

STEP5_PRESENTATION_MARKER = prior.STEP5_PRESENTATION_MARKER
STEP5_DATA_MARKER = prior.STEP5_DATA_MARKER
STEP5_VISUAL_MARKER = prior.STEP5_VISUAL_MARKER
STEP6_PRESENTATION_MARKER = prior.STEP6_PRESENTATION_MARKER
STEP6_DATA_MARKER = prior.STEP6_DATA_MARKER
STEP6_VISUAL_MARKER = prior.STEP6_VISUAL_MARKER
STEP6_DEPLOYMENT_MARKER = prior.STEP6_DEPLOYMENT_MARKER
STEP6_VISUAL_PARITY_MARKER = prior.STEP6_VISUAL_PARITY_MARKER
STEP6_CERT_SURFACE_MARKER = prior.STEP6_CERT_SURFACE_MARKER

_step6_snapshot_row = prior._step6_snapshot_row
_step6_snapshot_bundle = prior._step6_snapshot_bundle

_DATA_OWNER_LOCK = RLock()



def _game_total_hero_html_v20(
    raw: Mapping[str, Any],
    final: Mapping[str, Any],
    display_game: Mapping[str, Any],
    statuses: Mapping[int, str],
    ready_count: int,
) -> str:
    projected_value = (
        final.get("projected_combined_total")
        if final.get("ready")
        else raw.get("projected_combined_total")
    )
    projected = compact_owner._num(projected_value)
    market = compact_owner._market_total(display_game)
    grade = compact_owner._clean(final.get("grade")) if final.get("ready") else "—"
    strength = compact_owner._pct(final.get("forecast_strength")) if final.get("ready") else "—"

    if market is None:
        market_text = "—"
        lean = "Market total unavailable"
        lean_sub = "No verified line • model remains independent"
    else:
        market_text = compact_owner._num(market)
        if projected_value is None:
            lean = "Projection unavailable"
            lean_sub = "Market verified • model projection pending"
        else:
            edge = float(projected_value) - float(market)
            if edge > 0:
                lean = f"Over +{abs(edge):.1f}"
                lean_sub = "Slight Over Lean" if abs(edge) < 2 else "Over Lean"
            elif edge < 0:
                lean = f"Under -{abs(edge):.1f}"
                lean_sub = "Slight Under Lean" if abs(edge) < 2 else "Under Lean"
            else:
                lean, lean_sub = "Even 0.0", "No directional edge"

    checked = max(0, min(12, int(ready_count)))
    pending = max(0, 12 - checked)
    data_copy = (
        "All core checks ready"
        if checked == 12
        else f"{pending} required checks pending"
    )

    return f"""
<div class="gt159-total" data-testid="gt159-game-total-hero"
     data-ready-count="{checked}" data-total-checks="12">
  <div class="gt159-totalhead"><span>⬢ GAME TOTAL</span><span class="gt159-cert">🛡 5M CERTIFIED</span></div>
  <div class="gt159-totalgrid">
    <div class="gt159-totalmetric hero"><span>Projected Total</span><b>{escape(projected)}</b></div>
    <div class="gt159-totalmetric"><span>Market Total</span><b>{escape(market_text)}</b></div>
    <div class="gt159-totalmetric lean"><span>Over / Under Lean</span><b>{escape(lean)}</b><small>{escape(lean_sub)}</small></div>
    <div class="gt159-totalmetric"><span>Confidence</span><b>{escape(strength)}</b><div class="gt159-grade">Grade: {escape(grade or '—')}</div></div>
  </div>
  <div class="gt159-badges">
    <div class="gt159-badge">⭐ <strong>5M Certified</strong><br>Model validated • Real data only</div>
    <div class="gt159-badge purple">▥ <strong>0.0% sportsbook projection influence</strong><br>Independent analysis</div>
    <div class="gt159-badge green">✓ <strong>{checked}/12 Data Check</strong><br>{escape(data_copy)}</div>
  </div>
</div>"""


def _render_with_v20_slate(callback, *args, **kwargs):
    """Route only the compact page's data owner + hero contract to Step-1 V20."""
    with _DATA_OWNER_LOCK:
        original_slate = compact_owner.frozen_page.slate
        original_hero = compact_owner._game_total_hero_html
        compact_owner.frozen_page.slate = slate_v2
        compact_owner._game_total_hero_html = _game_total_hero_html_v20
        try:
            return callback(*args, **kwargs)
        finally:
            compact_owner._game_total_hero_html = original_hero
            compact_owner.frozen_page.slate = original_slate


def render_step6_cert_surface() -> None:
    # Step 6 certification is already frozen/green and does not need Slate V2.
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _render_with_v20_slate(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(
            f"Page V20 received unsupported market: {market}"
        )
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP5_DATA_MARKER",
    "STEP5_PRESENTATION_MARKER",
    "STEP5_VISUAL_MARKER",
    "STEP6_CERT_SURFACE_MARKER",
    "STEP6_DATA_MARKER",
    "STEP6_DEPLOYMENT_MARKER",
    "STEP6_PRESENTATION_MARKER",
    "STEP6_VISUAL_MARKER",
    "STEP6_VISUAL_PARITY_MARKER",
    "_game_total_hero_html_v20",
    "_step6_snapshot_bundle",
    "_step6_snapshot_row",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
