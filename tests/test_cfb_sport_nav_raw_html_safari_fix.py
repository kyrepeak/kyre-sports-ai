from __future__ import annotations

import cfb_game_total_clean_page_v33 as page


def test_non_current_sport_cards_do_not_create_markdown_code_blocks() -> None:
    for sport in ("NFL", "MLB", "WNBA"):
        html = page._sport_panel(sport)

        # Regression: an empty selected-badge placeholder previously left a
        # blank line before an indented <div>, which Markdown rendered as code.
        anchor_start = html.index('<a class="gt229-card')
        icon_start = html.index('<div class="gt229-icon"', anchor_start)
        between = html[anchor_start:icon_start]

        assert "\n    \n" not in between
        assert 'target="_self">' in between


def test_current_cfb_card_still_keeps_current_badge_and_dropdown() -> None:
    html = page._sport_panel("CFB")
    assert '<span class="gt229-active">Current</span>' in html
    assert '<details class="gt232-dropdown" data-dropdown="CFB" open>' in html


def test_all_cards_keep_real_same_app_links() -> None:
    html = page._sport_dropdown_nav_html()
    for sport in ("NFL", "CFB", "MLB", "WNBA"):
        assert f'data-sport="{sport}"' in html
        assert f'?{page.SPORT_JUMP_QUERY_KEY}={sport}' in html
