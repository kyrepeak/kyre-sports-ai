from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import math

from nfl_daily_picks_core_v1 import (
    DailyPickCandidate,
    MarketLoadResult,
    candidate_is_eligible,
    market_status_from_results,
)

NOW = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)


def candidate(**changes):
    base = DailyPickCandidate(
        market_id="passing-yards",
        market_label="Passing Yards",
        game_id="401772345",
        game_date=date(2026, 10, 18),
        kickoff_at=NOW + timedelta(hours=3),
        team_id="HOU",
        opponent_team_id="JAX",
        athlete_id="4431611",
        subject_label="C.J. Stroud",
        matchup_label="HOU at JAX",
        side="OVER",
        market_line=247.5,
        model_projection=263.2,
        model_probability=0.61,
        edge_value=15.7,
        source_ready=True,
        source_fresh_at=NOW - timedelta(seconds=20),
        source_age_seconds=20.0,
        data_quality=0.93,
        uncertainty=0.18,
        source_version="nfl_passing_yards_hub_v42",
        reason_components=("Recent volume supports the projection",),
        source_grade="QUALIFIED",
        source_state="READY",
        freshness_limit_seconds=120.0,
    )
    return replace(base, **changes)


def test_ready_fresh_exact_identity_future_candidate_passes():
    assert candidate_is_eligible(candidate(), now_utc=NOW) == (True, "ELIGIBLE")


def test_kickoff_at_or_before_now_fails_closed():
    assert candidate_is_eligible(candidate(kickoff_at=NOW), now_utc=NOW)[1] == "KICKED_OFF"
    assert candidate_is_eligible(candidate(kickoff_at=NOW - timedelta(seconds=1)), now_utc=NOW)[1] == "KICKED_OFF"


def test_source_not_ready_and_blocked_states_fail_closed():
    assert candidate_is_eligible(candidate(source_ready=False), now_utc=NOW)[1] == "SOURCE_NOT_READY"
    for state in ("GATED", "NO PLAY", "UNAVAILABLE", "STALE"):
        ok, reason = candidate_is_eligible(candidate(source_state=state), now_utc=NOW)
        assert ok is False
        assert reason == f"SOURCE_{state.replace(' ', '_')}"


def test_non_finite_probability_or_required_line_fails():
    assert candidate_is_eligible(candidate(model_probability=math.nan), now_utc=NOW)[1] == "INVALID_PROBABILITY"
    assert candidate_is_eligible(candidate(market_line=None), now_utc=NOW)[1] == "MISSING_MARKET_LINE"


def test_player_props_require_exact_athlete_id_but_team_markets_do_not():
    assert candidate_is_eligible(candidate(athlete_id=None), now_utc=NOW)[1] == "MISSING_ATHLETE_ID"
    moneyline = candidate(
        market_id="moneyline",
        market_label="Moneyline",
        athlete_id=None,
        subject_label="Houston Texans",
        side="HOU",
        market_line=None,
    )
    assert candidate_is_eligible(moneyline, now_utc=NOW) == (True, "ELIGIBLE")


def test_stale_age_beyond_candidate_limit_fails():
    ok, reason = candidate_is_eligible(
        candidate(source_age_seconds=121.0, freshness_limit_seconds=120.0),
        now_utc=NOW,
    )
    assert ok is False
    assert reason == "STALE"


def test_six_market_statuses_are_independent():
    results = tuple(
        MarketLoadResult(market_id=market_id, status=status, candidates=(), source_version="v", fresh_at=NOW, diagnostic="")
        for market_id, status in (
            ("moneyline", "READY"),
            ("spread", "READY"),
            ("game-total", "STALE"),
            ("passing-yards", "READY"),
            ("rushing-yards", "UNAVAILABLE"),
            ("receiving-yards", "ERROR"),
        )
    )
    assert market_status_from_results(results) == {
        "moneyline": "READY",
        "spread": "READY",
        "game-total": "STALE",
        "passing-yards": "READY",
        "rushing-yards": "UNAVAILABLE",
        "receiving-yards": "ERROR",
    }
