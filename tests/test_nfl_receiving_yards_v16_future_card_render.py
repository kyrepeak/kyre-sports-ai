from __future__ import annotations

from pathlib import Path

import pytest


BUG_SAMPLE = """
    <article class=\"krecv2-card\">
      <div class=\"krecv2-top\">Receiver A</div>
    </article>
    """


def test_future_receiver_card_html_is_normalized_for_markdown_rendering() -> None:
    from nfl_receiving_yards_future_card_render_v1 import normalize_receiver_identity_card_html

    normalized = normalize_receiver_identity_card_html(BUG_SAMPLE)

    assert normalized.startswith('<article class="krecv2-card">')
    assert normalized.endswith("</article>")
    assert "\n    <article" not in normalized


def test_multiple_future_receiver_cards_do_not_reintroduce_indented_article_blocks() -> None:
    from nfl_receiving_yards_future_card_render_v1 import normalize_receiver_identity_card_html

    cards = [normalize_receiver_identity_card_html(BUG_SAMPLE) for _ in range(3)]
    joined = '<div class="krecv2-grid">' + "".join(cards) + "</div>"

    assert joined.count('<article class="krecv2-card">') == 3
    assert "\n    <article" not in joined


def test_v16_wraps_v15_and_patches_the_frozen_v3_base_card_hook() -> None:
    source = Path("nfl_receiving_yards_hub_v16.py").read_text()

    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v15"' in source
    assert 'FROZEN_BASE_CARD_OWNER = "nfl_receiving_yards_hub_v3"' in source
    assert "base_page._ORIGINAL_PLAYER_CARD_V2" in source
    assert "normalize_receiver_identity_card_html" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_router_v147_advances_only_receiving_yards_to_v16() -> None:
    source = Path("streamlit_memory_lazy_router_v147.py").read_text()

    assert "nfl_receiving_yards_hub_v16" in source
    assert "streamlit_memory_lazy_router_v146" in source
    assert 'market == "Receiving Yards"' in source or 'market_name == "Receiving Yards"' in source


def test_app_bootstraps_router_v147() -> None:
    source = Path("app.py").read_text()

    assert "streamlit_memory_lazy_router_v147" in source
    assert "STREAMLIT_MAIN_V147_NFL_RECEIVING_YARDS_FUTURE_CARD_RENDER_FIX_2026-09-16" in source
