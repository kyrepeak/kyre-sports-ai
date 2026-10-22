from __future__ import annotations

import json

from sports_api.collectors.cfb_action_network_game_markets_v1 import (
    match_action_rows_to_games,
    parse_action_network_html,
)


def _row(side: str, *, value=None, odds=-110):
    row = {"side": side, "line_status": "normal", "is_live": False, "odds": odds}
    if value is not None:
        row["value"] = value
    return row


def test_action_parser_preserves_one_complete_named_book_quote():
    data = {
        "props": {
            "pageProps": {
                "allBooks": {"15": {"display_name": "DraftKings"}},
                "scoreboardResponse": {
                    "games": [
                        {
                            "id": 777,
                            "away_team_id": 1,
                            "home_team_id": 2,
                            "start_time": "2026-10-24T19:30:00Z",
                            "teams": [
                                {"id": 1, "full_name": "Western Michigan"},
                                {"id": 2, "full_name": "Toledo"},
                            ],
                            "markets": {
                                "15": {
                                    "event": {
                                        "moneyline": [_row("away", odds=230), _row("home", odds=-285)],
                                        "spread": [_row("away", value=7.5, odds=-108), _row("home", value=-7.5, odds=-112)],
                                        "total": [_row("over", value=52.5, odds=-105), _row("under", value=52.5, odds=-115)],
                                    }
                                }
                            },
                        }
                    ]
                },
            }
        }
    }
    html = '<html><script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + '</script></html>'
    rows = parse_action_network_html(html, observed_at_utc="2026-10-22T08:00:00+00:00")
    assert len(rows) == 1
    row = rows[0]
    assert row["sportsbook"] == "DraftKings"
    assert row["total_line"] == 52.5
    assert row["over_price"] == -105
    assert row["under_price"] == -115
    assert row["away_spread"] == 7.5
    assert row["home_spread"] == -7.5
    assert row["away_moneyline"] == 230
    assert row["home_moneyline"] == -285
    assert row["source_provider"] == "Action Network"


def test_action_matcher_handles_ncaa_abbreviation_without_guessing_game_id():
    game = {
        "game_id": "6603830",
        "away_team": "Western Mich.",
        "home_team": "Toledo",
        "kickoff_iso": "2026-10-24T15:30:00-04:00",
    }
    quote = {
        "sportsbook": "DraftKings",
        "provider_event_id": "777",
        "provider_market_id": "action:15:event",
        "away_team": "Western Michigan",
        "home_team": "Toledo",
        "start_time_utc": "2026-10-24T19:30:00Z",
        "total_line": 52.5,
    }
    matched = match_action_rows_to_games([game], [quote])
    assert list(matched) == ["6603830"]
    assert matched["6603830"][0]["provider_event_id"] == "777"
