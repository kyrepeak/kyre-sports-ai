"""MLB Pitcher Strikeouts O/U V1.0.10 — Top-5 intelligence HTML render repair.

Presentation-only repair on top of V1.0.9. Keeps the existing Strongest Pitcher
Strikeout O/U Top-5 board, ranking, projection math, workload/opponent-K model,
sportsbook parsing, line grading and Monte Carlo unchanged. Only removes Markdown
code-block indentation from the additive Top-5 intelligence HTML.
"""
from __future__ import annotations

from textwrap import dedent

import streamlit as st

import mlb_pitcher_k_hub_v109 as v109
import mlb_pitcher_k_hub_v101 as v101

engine = v109.engine
MODEL_VERSION = "Pitcher K V1.0.10"

# V1.0.9 saved the pre-intelligence card renderer here. Use that exact renderer
# so we do not stack the broken V1.0.9 HTML fragment on top of itself.
_base_card = v109._base_card


def _clean_intelligence_html(r):
    """Return V1.0.9 intelligence with no leading 4-space Markdown indentation."""
    raw = v109._intelligence_html(r)
    if not raw:
        return ""
    return dedent(str(raw)).strip()


def _card_with_top5_intelligence_clean(r, rank):
    html = _base_card(r, rank)
    try:
        intel = _clean_intelligence_html(r)
    except Exception:
        intel = ""
    if not intel:
        return html

    # Keep the intelligence inside the existing ranked card. The fragment starts
    # flush-left so Streamlit/Markdown cannot reinterpret it as a code block.
    marker = "</div>"
    pos = html.rfind(marker)
    if pos < 0:
        return f"{html}{intel}"
    return f"{html[:pos]}{intel}{html[pos:]}"


# The production renderer calls this symbol only for the ranked/graded Top-5 cards.
v101._card = _card_with_top5_intelligence_clean


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    # Reuse V1.0.9 styling/data helpers; replace only the card renderer above.
    original_markdown = st.markdown

    def _version_markdown(body, *args, **kwargs):
        if isinstance(body, str):
            body = body.replace("Pitcher Strikeouts O/U — V1.0.9", "Pitcher Strikeouts O/U — V1.0.10")
            body = body.replace("Pitcher Strikeouts O/U — V1.0.1", "Pitcher Strikeouts O/U — V1.0.10")
        return original_markdown(body, *args, **kwargs)

    st.markdown = _version_markdown
    try:
        return v109.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.markdown = original_markdown
