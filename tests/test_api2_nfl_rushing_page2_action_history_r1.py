from __future__ import annotations

import sports_api.nfl_rushing_yards_page2_live_repair_v1 as repair


def test_action_player_url_discovery_accepts_no_trailing_slash() -> None:
    html = '''
    <a href="/nfl/players/bijan-robinson-241851-2">Bijan Robinson</a>
    <a href="/nfl/players/javonte-williams-166333-2">Javonte Williams</a>
    <a href="/nfl/players/saquon-barkley-166334-2/">Saquon Barkley</a>
    '''
    assert repair._discover_action_player_url(html, player_name="Javonte Williams") == (
        "https://www.actionnetwork.com/nfl/players/javonte-williams-166333-2"
    )
    assert repair._discover_action_player_url(html, player_name="Saquon Barkley") == (
        "https://www.actionnetwork.com/nfl/players/saquon-barkley-166334-2"
    )


def test_action_rushing_open_current_parses_public_player_page_text() -> None:
    text = "Javonte Williams Dallas Cowboys RB Popular Markets Rush Yds u68.5 o64.5-114 u64.5-115 Rec Yds u16.5 o13.5-115"
    row = repair.parse_action_rushing_open_current(text, player_name="Javonte Williams")
    assert row["opening_line"] == 68.5
    assert row["current_line"] == 64.5
    assert row["movement"] == -4.0
    assert row["movement_status"] == "ACTION NETWORK 68.5 → 64.5 (-4.0)"


def test_action_history_repair_stays_provider_independent() -> None:
    assert repair.VERSION == "NFL_RUSHING_PAGE2_LIVE_ACCEPTANCE_REPAIR_V2_ACTION_HISTORY"
