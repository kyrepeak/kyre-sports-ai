"""WNBA Rebounds V3.1.1 — visual-card polish.

Preserves the complete V3.1 visual Top-5 card layer, V3.0 Production Readiness
Guard and Steps 1–20 model/market chain. This patch is presentation-only:
- removes player initials from the headshot circle so the face is unobstructed;
- gives the #1 selection a subtle BEST PICK treatment;
- leaves all data, projections, Monte Carlo, probabilities, EV, rankings,
  qualification, freshness and production-readiness rules unchanged.
"""
from __future__ import annotations

import re

import wnba_rebounds_hub_v31 as base

MODEL_VERSION = "WNBA REBOUNDS V3.1.1 • CLEAN PLAYER FACES + TOP-PICK POLISH • MODEL PRESERVED"

_original_card_html = base._card_html


def _clean_card_html(row: dict) -> str:
    """Presentation-only transform of the verified V3.1 card HTML."""
    markup = _original_card_html(row)

    # Remove the initials overlay from the player portrait. The ESPN headshot
    # remains the only content inside the circular face area.
    markup = re.sub(
        r'(<div class="kr-reb-avatar"[^>]*>)\s*<span>.*?</span>\s*(</div>)',
        r'\1\2',
        markup,
        count=1,
        flags=re.S,
    )

    # Small visual emphasis for rank #1 only. No ranking logic changes.
    try:
        rank = int(float(row.get("rank") or 0))
    except Exception:
        rank = 0
    if rank == 1:
        markup = markup.replace(
            '<article class="kr-reb-card">',
            '<article class="kr-reb-card" style="border-color:#49cfff;box-shadow:0 0 0 1px rgba(73,207,255,.18),0 14px 34px rgba(0,0,0,.24)">',
            1,
        )
        markup = markup.replace(
            '🏀 TOP REB #1',
            '⭐ BEST PICK • TOP REB #1',
            1,
        )
    return markup


# V3.1's renderer resolves _card_html from its module globals at runtime.
# Patching only that presentation helper avoids copying/rebuilding the model.
base._card_html = _clean_card_html


def render_wnba_rebounds_hub(*args, **kwargs):
    return base.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
