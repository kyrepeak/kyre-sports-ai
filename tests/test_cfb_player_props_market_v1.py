from __future__ import annotations

from datetime import date


def _identity_index():
    import cfb_player_props_identity_v1 as identity
    p = identity.CanonicalPlayerIdentity(
        "12345", "77", "Jalen Example", "QB", "Example State", "EXS",
        (("sportsgameodds", "sgo-player-9"),),
    )
    return identity.build_identity_index([p])


def test_canonical_market_family_is_exact_and_unknown_market_rejected():
    import cfb_player_props_market_v1 as market

    supported = {
        "passing_yards", "rushing_yards", "receiving_yards",
        "receiving_receptions", "passing_touchdowns", "touchdowns",
    }
    assert {market.canonical_market_key(x) for x in supported} == supported
    assert market.canonical_market_key("fantasy_points") is None


def test_verified_observation_normalizes_identity_line_price_and_provenance():
    import cfb_player_props_market_v1 as market

    raw = {
        "official_game_id": "401999001",
        "provider": "SportsGameOdds",
        "provider_event_id": "evt-1",
        "provider_player_id": "sgo-player-9",
        "provider_market_id": "odd-1",
        "stat_id": "passing_yards",
        "sportsbook": "FanDuel",
        "side": "over",
        "line": 275.5,
        "price": -110,
        "observed_at_utc": "2026-10-20T04:00:00Z",
    }
    obs = market.normalize_prop_observation(raw, _identity_index())
    assert obs is not None
    assert obs.official_game_id == "401999001"
    assert obs.canonical_player_id == "12345"
    assert obs.market_key == "passing_yards"
    assert obs.sportsbook == "FanDuel"
    assert obs.side == "over"
    assert obs.line == 275.5
    assert obs.price == -110
    assert obs.identity_verified is True
    assert obs.provider_event_id == "evt-1"


def test_unverified_identity_nonfinite_line_and_bad_side_fail_closed():
    import cfb_player_props_market_v1 as market

    base = {
        "official_game_id": "401999001", "provider": "SportsGameOdds",
        "provider_player_id": "unknown", "stat_id": "passing_yards",
        "sportsbook": "FanDuel", "side": "over", "line": 250.5,
        "observed_at_utc": "2026-10-20T04:00:00Z",
    }
    assert market.normalize_prop_observation(base, _identity_index()) is None
    bad = dict(base, provider_player_id="sgo-player-9", line=float("nan"))
    assert market.normalize_prop_observation(bad, _identity_index()) is None
    bad = dict(base, provider_player_id="sgo-player-9", side="yes")
    assert market.normalize_prop_observation(bad, _identity_index()) is None


def test_merge_keeps_freshest_verified_quote_per_book_side_and_provenance():
    import cfb_player_props_market_v1 as market

    idx = _identity_index()
    common = {
        "official_game_id": "401999001", "provider_player_id": "sgo-player-9",
        "stat_id": "passing_yards", "sportsbook": "FanDuel", "side": "over",
        "line": 275.5, "price": -110,
    }
    old = market.normalize_prop_observation(
        dict(common, provider="fallback", provider_event_id="old", observed_at_utc="2026-10-20T03:00:00Z"), idx
    )
    fresh = market.normalize_prop_observation(
        dict(common, provider="SportsGameOdds", provider_event_id="fresh", line=276.5, observed_at_utc="2026-10-20T04:00:00Z"), idx
    )
    rows = market.merge_prop_observations([old], [fresh])
    assert len(rows) == 1
    assert rows[0].line == 276.5
    assert rows[0].provider == "SportsGameOdds"
    assert rows[0].provider_event_id == "fresh"


def test_sgo_filter_uses_ncaaf_and_six_player_prop_markets(monkeypatch):
    import cfb_player_props_sportsgameodds_v1 as sgo

    odd_ids = sgo.build_odd_id_filter()
    for stat in (
        "passing_yards", "rushing_yards", "receiving_yards",
        "receiving_receptions", "passing_touchdowns", "touchdowns",
    ):
        assert f"{stat}-PLAYER_ID-game-ou-over" in odd_ids
        assert f"{stat}-PLAYER_ID-game-ou-under" in odd_ids
    assert sgo.SGO_LEAGUE_ID == "NCAAF"


def test_fanduel_secondary_returns_empty_when_surface_has_no_compatible_player_props(monkeypatch):
    import cfb_player_props_fanduel_v1 as fd

    monkeypatch.setattr(fd, "_fetch_payload", lambda: {"attachments": {"events": {}, "markets": {}}})
    assert fd.fetch_fanduel_cfb_player_props([]) == []
