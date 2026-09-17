from datetime import date

import cfb_game_total_clean_page_v15 as page


def test_v164_enriches_selector_from_official_games_payload():
    games = [
        {
            "away_team": "Example State",
            "home_team": "Example Tech",
            "game_date": "2026-09-19",
        }
    ]
    payload = {
        "verified": True,
        "sportsbook_projection_influence_pct": 0.0,
        "games": [
            {
                "event_id": "401752999",
                "game_date": "2026-09-19",
                "away_team": "Example State Wildcats",
                "home_team": "Example Tech",
                "venue": "Example Stadium",
                "broadcast": "ESPN",
            }
        ],
    }

    matched = page._enrich_selector_ids_from_api(
        games,
        payload,
        date(2026, 9, 19),
    )

    assert matched == 1
    assert games[0]["espn_event_id"] == "401752999"
    assert games[0]["selector_identity_source"] == page.SELECTOR_IDENTITY_SOURCE
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_v164_fails_closed_on_ambiguous_identity():
    games = [{"away_team": "Example State", "home_team": "Example Tech"}]
    payload = {
        "verified": True,
        "games": [
            {
                "event_id": "401752999",
                "game_date": "2026-09-19",
                "away_team": "Example State",
                "home_team": "Example Tech",
            },
            {
                "event_id": "401753001",
                "game_date": "2026-09-19",
                "away_team": "Example State",
                "home_team": "Example Tech",
            },
        ],
    }

    matched = page._enrich_selector_ids_from_api(
        games,
        payload,
        date(2026, 9, 19),
    )

    assert matched == 0
    assert "espn_event_id" not in games[0]
