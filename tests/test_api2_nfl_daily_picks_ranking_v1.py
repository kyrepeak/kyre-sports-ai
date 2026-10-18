from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import random

from nfl_daily_picks_core_v1 import DailyPickCandidate
import nfl_daily_picks_ranking_v1 as ranking

NOW = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 18)


def pick(i=1, **changes):
    market_id = changes.pop("market_id", "spread")
    team_id = changes.pop("team_id", f"T{i:02d}")
    age = changes.pop("source_age_seconds", 20.0)
    base = DailyPickCandidate(
        market_id=market_id,
        market_label={"spread":"Spread","moneyline":"Moneyline","passing-yards":"Passing Yards"}.get(market_id, market_id),
        game_id=changes.pop("game_id", f"G{i:02d}"),
        game_date=DAY,
        kickoff_at=NOW + timedelta(hours=3+i),
        team_id=team_id,
        opponent_team_id=changes.pop("opponent_team_id", f"O{i:02d}"),
        athlete_id=changes.pop("athlete_id", "QB1" if market_id == "passing-yards" else None),
        subject_label=changes.pop("subject_label", team_id),
        matchup_label=changes.pop("matchup_label", f"{team_id} at O{i:02d}"),
        side=changes.pop("side", "AWAY" if market_id in {"spread","moneyline"} else "OVER"),
        market_line=changes.pop("market_line", None if market_id == "moneyline" else 2.5),
        model_projection=changes.pop("model_projection", None if market_id == "moneyline" else -1.0),
        model_probability=changes.pop("model_probability", 0.60),
        edge_value=changes.pop("edge_value", 0.05 if market_id == "moneyline" else 3.0),
        source_ready=True,
        source_fresh_at=NOW - timedelta(seconds=age),
        source_age_seconds=age,
        data_quality=changes.pop("data_quality", 0.90),
        uncertainty=changes.pop("uncertainty", 0.10),
        source_version="source-v1",
        reason_components=("reason",),
        source_grade="A",
        source_state="READY",
        freshness_limit_seconds=120.0,
    )
    return replace(base, **changes)


def test_stronger_probability_edge_freshness_and_quality_rank_higher():
    weak = pick(1, model_probability=0.54, edge_value=1.0, data_quality=0.70, source_age_seconds=100.0)
    strong = pick(2, model_probability=0.68, edge_value=5.0, data_quality=0.96, source_age_seconds=5.0)
    ranked = ranking.rank_daily_picks([weak, strong], now_utc=NOW)
    assert ranked[0] == strong
    assert ranking.normalized_pick_score(strong) > ranking.normalized_pick_score(weak)


def test_ranking_does_not_mutate_inputs():
    candidates = [pick(1), pick(2)]
    before = tuple(candidates)
    ranking.rank_daily_picks(candidates, now_utc=NOW)
    assert tuple(candidates) == before


def test_pure_best_ten_has_no_quota_or_filler():
    twelve = [pick(i, model_probability=0.51 + i * 0.01) for i in range(1, 13)]
    assert len(ranking.rank_daily_picks(twelve, now_utc=NOW, limit=10)) == 10
    seven = [pick(i) for i in range(1, 8)]
    assert len(ranking.rank_daily_picks(seven, now_utc=NOW, limit=10)) == 7


def test_same_team_moneyline_and_spread_redundancy_keeps_higher_ranked():
    ml = pick(1, market_id="moneyline", game_id="G1", team_id="HOU", opponent_team_id="JAX", side="AWAY", model_probability=0.65, edge_value=0.08)
    spread = pick(2, market_id="spread", game_id="G1", team_id="HOU", opponent_team_id="JAX", side="AWAY", model_probability=0.57, edge_value=2.0)
    ranked = ranking.rank_daily_picks([spread, ml], now_utc=NOW)
    assert ranked == (ml,)
    assert ranking.picks_redundant(ml, spread)


def test_contradictory_same_market_directions_cannot_coexist():
    away = pick(1, market_id="spread", game_id="G1", team_id="HOU", opponent_team_id="JAX", side="AWAY", model_probability=0.62)
    home = pick(2, market_id="spread", game_id="G1", team_id="JAX", opponent_team_id="HOU", side="HOME", model_probability=0.38)
    ranked = ranking.rank_daily_picks([home, away], now_utc=NOW)
    assert len(ranked) == 1
    assert ranked[0] == away
    assert ranking.picks_conflict(away, home)


def test_distinct_player_prop_and_team_pick_can_coexist_same_game():
    team = pick(1, market_id="spread", game_id="G1", team_id="HOU", opponent_team_id="JAX", side="AWAY")
    player = pick(2, market_id="passing-yards", game_id="G1", team_id="HOU", opponent_team_id="JAX", athlete_id="4431611", subject_label="C.J. Stroud", side="OVER", market_line=247.5, model_probability=0.63, edge_value=6.1)
    ranked = ranking.rank_daily_picks([team, player], now_utc=NOW)
    assert set(ranked) == {team, player}
    assert not ranking.picks_conflict(team, player)
    assert not ranking.picks_redundant(team, player)


def test_ties_use_quality_freshness_uncertainty_edge_then_stable_identity():
    low_q = pick(1, model_probability=0.60, edge_value=2.0, data_quality=0.70)
    high_q = pick(2, model_probability=0.60, edge_value=2.0, data_quality=0.95)
    assert ranking.rank_daily_picks([low_q, high_q], now_utc=NOW)[0] == high_q

    stale = pick(3, model_probability=0.60, edge_value=2.0, data_quality=0.90, source_age_seconds=100.0)
    fresh = pick(4, model_probability=0.60, edge_value=2.0, data_quality=0.90, source_age_seconds=5.0)
    assert ranking.rank_daily_picks([stale, fresh], now_utc=NOW)[0] == fresh

    uncertain = pick(5, model_probability=0.60, edge_value=2.0, data_quality=0.90, uncertainty=0.30)
    certain = pick(6, model_probability=0.60, edge_value=2.0, data_quality=0.90, uncertainty=0.05)
    assert ranking.rank_daily_picks([uncertain, certain], now_utc=NOW)[0] == certain


def test_shuffled_input_produces_same_final_order():
    candidates = [pick(i, model_probability=0.52 + 0.01 * i, data_quality=0.70 + 0.01 * i) for i in range(1, 9)]
    expected = ranking.rank_daily_picks(candidates, now_utc=NOW)
    shuffled = candidates[:]
    random.Random(42).shuffle(shuffled)
    assert ranking.rank_daily_picks(shuffled, now_utc=NOW) == expected
