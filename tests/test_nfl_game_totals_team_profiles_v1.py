from datetime import datetime, timezone

import pytest

from sports_api.collectors import nfl_game_totals_team_profiles_v1 as profiles


def _event(event_id, date_text, team_id, opponent_id, pf, pa, *, completed=True):
    return {
        "id": str(event_id),
        "date": date_text,
        "status": {"type": {"state": "post" if completed else "pre", "completed": completed}},
        "competitions": [
            {
                "id": str(event_id),
                "date": date_text,
                "competitors": [
                    {
                        "homeAway": "away",
                        "team": {"id": str(team_id), "abbreviation": "DET"},
                        "score": str(pf),
                    },
                    {
                        "homeAway": "home",
                        "team": {"id": str(opponent_id), "abbreviation": "BUF"},
                        "score": str(pa),
                    },
                ],
            }
        ],
    }


def _schedule(team_id="8", n=12, *, start_year=2025, base_pf=24, base_pa=20):
    events = []
    for i in range(n):
        events.append(
            _event(
                500000000 + i,
                f"{start_year}-{9 + (i // 4):02d}-{1 + (i % 4) * 7:02d}T17:00:00Z",
                team_id,
                "2" if str(team_id) != "2" else "8",
                base_pf + (i % 3),
                base_pa + (i % 2),
            )
        )
    return {"events": events}


def test_completed_schedule_parser_uses_exact_team_id_and_cutoff():
    payload = _schedule(n=3, start_year=2026)
    payload["events"].append(_event("999999999", "2026-10-20T17:00:00Z", "8", "2", 35, 10, completed=False))
    rows = profiles.parse_completed_regular_schedule(
        payload,
        "8",
        before_utc=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    assert len(rows) == 3
    assert all(row["official_team_id"] == "8" for row in rows)
    assert all(row["kickoff_utc"] < "2026-10-01" for row in rows)


def test_scoring_summary_contains_ppg_papg_and_recent_six():
    rows = [
        {"pf": 20.0, "pa": 17.0},
        {"pf": 24.0, "pa": 21.0},
        {"pf": 28.0, "pa": 14.0},
    ]
    summary = profiles.summarize_completed_games(rows)
    assert summary["games"] == 3
    assert summary["ppg"] == 24.0
    assert summary["papg"] == pytest.approx(52.0 / 3.0)
    assert summary["recent6_pf_pg"] == 24.0
    assert summary["recent6_pa_pg"] == pytest.approx(52.0 / 3.0)


def test_prior_current_blend_uses_six_game_prior_weight():
    prior = {"games": 17, "ppg": 24.0, "papg": 20.0, "recent6_pf_pg": 25.0, "recent6_pa_pg": 19.0}
    current = {"games": 2, "ppg": 30.0, "papg": 22.0, "recent6_pf_pg": 30.0, "recent6_pa_pg": 22.0}
    out = profiles.blend_scoring_profiles(prior, current)
    assert out["current_weight"] == pytest.approx(0.25)
    assert out["ppg"] == pytest.approx((6 * 24.0 + 2 * 30.0) / 8.0)
    assert out["papg"] == pytest.approx((6 * 20.0 + 2 * 22.0) / 8.0)
    # With fewer than three current games, recent form remains prior-season anchored.
    assert out["recent6_pf_pg"] == 25.0
    assert out["recent6_pa_pg"] == 19.0


def test_collect_profile_is_exact_id_football_only_and_ready():
    def fetcher(team_id, season):
        if season == 2025:
            return _schedule(team_id, 12, start_year=2025), "fixture://espn-prior"
        if season == 2026:
            return _schedule(team_id, 2, start_year=2026, base_pf=30, base_pa=22), "fixture://espn-current"
        raise AssertionError(season)

    out = profiles.collect_team_scoring_profile(
        {"team_id": "8", "abbr": "DET", "name": "Detroit Lions"},
        "2026-10-01",
        fetcher=fetcher,
    )
    assert out["ready"] is True
    assert out["official_team_id"] == "8"
    assert out["abbr"] == "DET"
    assert out["prior_games"] == 12
    assert out["current_games"] == 2
    assert out["sportsbook_projection_influence"] == 0.0
    assert out["sportsbook_inputs"] == []
    assert "total" not in out
    assert "sportsbook" not in out


def test_collect_profile_fails_closed_below_prior_sample_minimum():
    def fetcher(team_id, season):
        return _schedule(team_id, 4, start_year=season), "fixture://espn"

    with pytest.raises(profiles.NFLGameTotalsTeamProfileError):
        profiles.collect_team_scoring_profile(
            {"team_id": "8", "abbr": "DET", "name": "Detroit Lions"},
            "2026-10-01",
            fetcher=fetcher,
        )


def test_parser_fails_closed_when_exact_team_is_missing():
    with pytest.raises(profiles.NFLGameTotalsTeamProfileError):
        profiles.parse_completed_regular_schedule(_schedule("8", 2), "999")
