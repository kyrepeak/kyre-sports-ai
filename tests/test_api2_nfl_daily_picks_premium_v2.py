from datetime import date, datetime, timedelta, timezone

import nfl_daily_picks_hub_v1 as hub
from nfl_daily_picks_core_v1 import DailyPickCandidate, MarketLoadResult

NOW = datetime(2026, 10, 18, 18, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 18)


def candidate(*, rank=1, market_id="passing-yards", athlete_id="4431611", team_id="HOU", opponent="JAX"):
    labels = {
        "moneyline": "Moneyline",
        "spread": "Spread",
        "game-total": "Game Total",
        "passing-yards": "Passing Yards",
        "rushing-yards": "Rushing Yards",
        "receiving-yards": "Receiving Yards",
    }
    subject = "C.J. Stroud" if athlete_id else "Houston Texans"
    line = None if market_id == "moneyline" else 247.5
    return DailyPickCandidate(
        market_id=market_id,
        market_label=labels[market_id],
        game_id="401772345",
        game_date=DAY,
        kickoff_at=NOW + timedelta(hours=4),
        team_id=team_id,
        opponent_team_id=opponent,
        athlete_id=athlete_id,
        subject_label=subject,
        matchup_label=f"{team_id} at {opponent}",
        side="OVER" if market_id not in {"moneyline", "spread"} else "AWAY",
        market_line=line,
        model_projection=263.2 if line is not None else None,
        model_probability=0.684,
        edge_value=7.8,
        source_ready=True,
        source_fresh_at=NOW - timedelta(seconds=42),
        source_age_seconds=42.0,
        data_quality=0.93,
        uncertainty=0.08,
        source_version="certified-source-v1",
        reason_components=(
            "Model probability clears the daily quality bar",
            "Projection creates a meaningful cushion versus the current market line",
            "Fresh exact-identity market context is verified",
        ),
        source_grade="CERTIFIED",
        source_state="READY",
        freshness_limit_seconds=300.0,
        metadata=(("line_open", 251.5), ("weather", "Dome"), ("risk_reason", "Market can move before kickoff.")),
    )


def test_exact_identity_visual_urls_are_product_safe():
    assert hub._team_logo_url("KC") == "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png"
    assert hub._team_logo_url("") == ""
    assert hub._player_headshot_url("4431611") == "https://a.espncdn.com/i/headshots/nfl/players/full/4431611.png"
    assert hub._player_headshot_url("QB1") == ""


def test_top_three_receive_distinct_product_badges():
    assert "BEST PICK TODAY" in hub._rank_badge(1)
    assert "STRONG EDGE" in hub._rank_badge(2)
    assert "TOP VALUE" in hub._rank_badge(3)
    assert hub._rank_badge(7) == "#7"


def test_internal_gated_state_is_not_exposed_as_page_inaccessible():
    assert hub._display_market_state("READY") == ("QUALIFIED NOW", "ready")
    label, css = hub._display_market_state("GATED")
    assert label == "CONNECTED • NO QUALIFIED PICK"
    assert css == "connected"
    assert "GATED" not in label
    assert hub._display_market_state("STALE")[0] == "REFRESHING"
    assert hub._display_market_state("ERROR")[0] == "SOURCE CHECK"


def test_premium_card_payload_has_visual_reason_edge_and_risk_context():
    card = hub._card_payload(candidate(), 1)
    assert card["team_logo_url"].endswith("/hou.png")
    assert card["opponent_logo_url"].endswith("/jax.png")
    assert card["player_headshot_url"].endswith("/4431611.png")
    assert card["rank_badge"].endswith("BEST PICK TODAY")
    assert len(card["why_points"]) >= 2
    assert card["risk_reason"] == "Market can move before kickoff."
    assert card["edge_label"] == "Projection Edge"
    assert card["edge_value"] == 15.7
    assert card["line_movement"] == "251.5 → 247.5"
    assert "Dome" in card["context_tags"]


def test_premium_card_html_is_human_facing_not_developer_readout():
    html = hub._card_html(hub._card_payload(candidate(), 1))
    assert "BEST PICK TODAY" in html
    assert "Why this is a top pick" in html
    assert "What could go wrong?" in html
    assert "Projection Edge" in html
    assert "Line move" in html
    assert "headshots/nfl/players/full/4431611.png" in html
    assert "teamlogos/nfl/500/hou.png" in html
    assert "teamlogos/nfl/500/jax.png" in html
    assert "Source verified" in html
    assert "Daily Picks score" not in html
    assert "certified-source-v1" not in html


def test_team_market_card_uses_team_logos_without_fake_player_image():
    team_pick = candidate(market_id="spread", athlete_id=None)
    html = hub._card_html(hub._card_payload(team_pick, 2))
    assert "STRONG EDGE" in html
    assert "teamlogos/nfl/500/hou.png" in html
    assert "teamlogos/nfl/500/jax.png" in html
    assert "headshots/nfl/players/full" not in html


def test_status_grid_shows_six_connected_market_surfaces_without_gated_word():
    statuses = {
        "moneyline": "GATED",
        "spread": "READY",
        "game-total": "GATED",
        "passing-yards": "GATED",
        "rushing-yards": "GATED",
        "receiving-yards": "GATED",
    }
    html = hub._status_html({"market_statuses": statuses})
    assert html.count("CONNECTED • NO QUALIFIED PICK") == 5
    assert "QUALIFIED NOW" in html
    assert "GATED" not in html


def test_board_reports_connected_markets_separately_from_qualified_markets(monkeypatch):
    results = tuple(
        MarketLoadResult(
            market_id=market_id,
            status="READY" if market_id == "spread" else "GATED",
            candidates=(candidate(market_id="spread", athlete_id=None),) if market_id == "spread" else (),
            source_version=f"{market_id}-v1",
            fresh_at=NOW,
            diagnostic="connected source owner",
        )
        for market_id in hub.MARKET_ORDER
    )
    monkeypatch.setattr(hub, "load_all_market_candidates", lambda day, now_utc, loaders=None: results)
    board = hub.build_daily_picks_board(DAY, now_utc=NOW)
    assert board["connected_market_count"] == 6
    assert board["healthy_market_count"] == 1
    assert board["candidate_count"] == 1


def test_future_games_only_rule_remains_locked():
    from nfl_daily_picks_core_v1 import candidate_is_eligible

    kicked = candidate()
    kicked = DailyPickCandidate(**{**kicked.__dict__, "kickoff_at": NOW})
    eligible, reason = candidate_is_eligible(kicked, now_utc=NOW)
    assert eligible is False
    assert reason == "KICKED_OFF"
