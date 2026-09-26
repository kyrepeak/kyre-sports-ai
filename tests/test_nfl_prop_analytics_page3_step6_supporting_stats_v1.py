from pathlib import Path

import nfl_prop_analytics_page3_supporting_stats_v1 as support

SUPPORT_SRC = Path("nfl_prop_analytics_page3_supporting_stats_v1.py").read_text()
PAGE_SRC = Path("nfl_prop_analytics_prop_page_v1.py").read_text()


def _summary(pass_yards, completions, attempts, pass_td, interceptions, rush_yards=12):
    return {
        "boxscore": {
            "players": [
                {
                    "team": {"id": "7"},
                    "statistics": [
                        {
                            "name": "passing",
                            "labels": ["C/ATT", "YDS", "TD", "INT"],
                            "athletes": [
                                {
                                    "athlete": {"id": "999001"},
                                    "stats": [f"{completions}/{attempts}", str(pass_yards), str(pass_td), str(interceptions)],
                                }
                            ],
                        },
                        {
                            "name": "rushing",
                            "labels": ["CAR", "YDS", "AVG", "TD", "LONG"],
                            "athletes": [
                                {
                                    "athlete": {"id": "999001"},
                                    "stats": ["4", str(rush_yards), "3.0", "0", "8"],
                                }
                            ],
                        },
                    ],
                }
            ]
        }
    }


def test_extract_qb_supporting_metrics_from_exact_athlete_boxscore():
    metrics = support.extract_event_metrics(_summary(300, 24, 36, 2, 1, 18), "999001")
    assert metrics["passing_yards"] == 300.0
    assert metrics["completions"] == 24.0
    assert metrics["attempts"] == 36.0
    assert round(metrics["completion_pct"], 1) == 66.7
    assert round(metrics["yards_per_attempt"], 2) == round(300 / 36, 2)
    assert metrics["passing_tds"] == 2.0
    assert metrics["interceptions"] == 1.0
    assert metrics["rushing_yards"] == 18.0


def test_average_and_median_modes_recalculate_same_verified_sample(monkeypatch):
    payloads = {
        "4011": _summary(300, 24, 36, 2, 1, 18),
        "4012": _summary(210, 18, 30, 1, 0, 9),
        "4013": _summary(390, 30, 45, 3, 2, 24),
    }
    monkeypatch.setattr(support, "_summary", lambda event_id: payloads[event_id])
    games = [
        {"official_event_id": "4011"},
        {"official_event_id": "4012"},
        {"official_event_id": "4013"},
    ]

    avg = support.load_supporting_stats(
        games=games,
        athlete_id="999001",
        market_key="passing_yards",
        mode="average",
    )
    med = support.load_supporting_stats(
        games=games,
        athlete_id="999001",
        market_key="passing_yards",
        mode="median",
    )

    assert avg["ready"] is True and med["ready"] is True
    assert avg["event_count"] == 3 == med["event_count"]
    assert [x["key"] for x in avg["metrics"]] == [
        "attempts",
        "completions",
        "completion_pct",
        "yards_per_attempt",
        "passing_tds",
        "interceptions",
    ]
    avg_attempts = next(x for x in avg["metrics"] if x["key"] == "attempts")
    med_attempts = next(x for x in med["metrics"] if x["key"] == "attempts")
    assert avg_attempts["value"] == 37.0
    assert med_attempts["value"] == 36.0


def test_receiving_profile_uses_prop_relevant_support_only(monkeypatch):
    summary = {
        "boxscore": {
            "players": [
                {
                    "team": {"id": "1"},
                    "statistics": [
                        {
                            "name": "receiving",
                            "labels": ["REC", "YDS", "AVG", "TD", "LONG", "TGTS"],
                            "athletes": [
                                {"athlete": {"id": "888"}, "stats": ["6", "84", "14.0", "1", "31", "9"]}
                            ],
                        }
                    ],
                }
            ]
        }
    }
    monkeypatch.setattr(support, "_summary", lambda event_id: summary)
    payload = support.load_supporting_stats(
        games=[{"official_event_id": "501"}],
        athlete_id="888",
        market_key="receiving_yards",
        mode="average",
    )
    keys = [row["key"] for row in payload["metrics"]]
    assert keys == [
        "targets",
        "receptions",
        "catch_pct",
        "yards_per_reception",
        "longest_reception",
        "receiving_tds",
    ]


def test_step6_contract_is_historical_context_only():
    for token in (
        'PAGE3_SUPPORT_STEP = 6',
        'PAGE3_SUPPORT_VERSION = "v1"',
        'SPORTSBOOK_LINE_SOURCE = False',
        'SPORTSBOOK_ODDS_LOGIC = False',
        'PROJECTION_LOGIC = False',
        'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
        'WAGER_ACTIONS = False',
        'Supporting stat summary',
        'options=["AVERAGE", "MEDIAN"]',
        'data-prop-page3-step6-supporting-stats="',
        'data-prop-page3-step6-mode="',
        'data-prop-page3-step6-metric="',
        'espn-exact-id-boxscores',
    ):
        assert token in SUPPORT_SRC, token


def test_prop_page_wires_step6_after_step5_chart():
    for token in (
        'from nfl_prop_analytics_page3_supporting_stats_v1 import (',
        'render_supporting_stats(',
        'games=history_payload.get("games") or []',
        'athlete_id=handoff["player_id"]',
        '"supporting_stats": supporting_stats',
    ):
        assert token in PAGE_SRC, token
    assert PAGE_SRC.index("render_game_chart(") < PAGE_SRC.index("render_supporting_stats(")
