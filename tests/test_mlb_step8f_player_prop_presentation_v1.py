from copy import deepcopy
import sys
from types import SimpleNamespace

import mlb_step8f_player_prop_presentation_v1 as step8f
from sports_api.mlb_step8a_player_prop_api_contract_v1 import (
    API_CONNECTED,
    HITS_RUNS_RBI,
    PITCHER_STRIKEOUTS,
    PLAYER_HITS,
    build_player_prop_api_state,
)


def _prop(game, player, market, *, line=5.5, over=-115, under=-105, name="FanDuel Display"):
    return {
        "official_game_id": game,
        "official_player_id": player,
        "player_name": name,
        "market_type": market,
        "line": line,
        "over_odds": over,
        "under_odds": under,
        "sportsbook": "FanDuel",
        "source_event_id": f"fd-event-{game}",
        "source_market_id": f"fd-market-{game}-{player}-{market}",
    }


def _payload(*props, collected="2026-09-01T01:00:00Z"):
    return {
        "data_type": "mlb_player_prop_api_response_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "collected_at_utc": collected,
        "props": list(props),
    }


def _fresh_state():
    state = step8f.build_step8f_player_prop_api_state(
        _payload(
            _prop(1001, 2001, PITCHER_STRIKEOUTS, line=6.5, over=-120, under=100),
            _prop(1002, 2002, PLAYER_HITS, line=0.5, over=-220, under=175),
            _prop(1003, 2003, HITS_RUNS_RBI, line=2.5, over=-110, under=-110),
        ),
        as_of_utc="2026-09-01T01:00:20Z",
        max_age_seconds=60,
    )
    assert state["integration_status"] == API_CONNECTED
    assert state["feed_fresh"] is True
    return state


def _result(game, player, name="Intentionally Different Model Name"):
    return {
        "game_pk": game,
        "player_id": player,
        "player_name": name,
        "projection_sentinel": 9.99,
        "probability_sentinel": 0.777,
        "rank_sentinel": 3,
        "sim": {"sentinel": 41, "p": 0.777},
    }


def test_step8f_state_uses_frozen_step8a_contract_and_proves_freshness():
    state = _fresh_state()
    assert state["match_method"] == "official_mlb_game_id_player_id_market_exact"
    assert state["player_name_matching_used"] is False
    assert state["fuzzy_matching_allowed"] is False
    assert state["sportsbook_price_model_input"] is False


def test_all_three_markets_decorate_only_on_exact_official_identity():
    state = _fresh_state()
    cases = (
        (PITCHER_STRIKEOUTS, _result(1001, 2001), "O/U 6.5", "Over -120", "Under +100"),
        (PLAYER_HITS, _result(1002, 2002), "O/U 0.5", "Over -220", "Under +175"),
        (HITS_RUNS_RBI, _result(1003, 2003), "O/U 2.5", "Over -110", "Under -110"),
    )
    for market, result, line, over, under in cases:
        before = deepcopy(result)
        html = step8f.decorate_card_html('<div class="card">BASE</div>', result, market, state)
        assert "STEP 8F" in html
        assert "EXACT ID MATCH" in html
        assert line in html
        assert over in html
        assert under in html
        assert result == before


def test_player_name_never_participates_in_presentation_identity():
    state = _fresh_state()
    result = _result(1002, 2002, name="NO NAME MATCH ON PURPOSE")
    html = step8f.decorate_card_html("<div>BASE</div>", result, PLAYER_HITS, state)
    assert "STEP 8F" in html
    assert "NO NAME MATCH ON PURPOSE" not in html


def test_wrong_official_player_id_returns_prior_html_byte_for_byte():
    state = _fresh_state()
    original = '<div class="card"><b>FROZEN</b></div>'
    result = _result(1002, 9999)
    assert step8f.decorate_card_html(original, result, PLAYER_HITS, state) == original


def test_wrong_official_game_id_returns_prior_html_byte_for_byte():
    state = _fresh_state()
    original = '<div class="card"><b>FROZEN</b></div>'
    result = _result(9999, 2002)
    assert step8f.decorate_card_html(original, result, PLAYER_HITS, state) == original


def test_market_cross_contamination_is_impossible():
    state = _fresh_state()
    original = "<div>FROZEN</div>"
    # Exact game/player exists as Player Hits, but must never satisfy H+R+RBI.
    result = _result(1002, 2002)
    assert step8f.decorate_card_html(original, result, HITS_RUNS_RBI, state) == original


def test_stale_api_state_preserves_prior_card_html_exactly():
    stale = step8f.build_step8f_player_prop_api_state(
        _payload(_prop(1002, 2002, PLAYER_HITS), collected="2026-09-01T00:00:00Z"),
        as_of_utc="2026-09-01T01:00:00Z",
        max_age_seconds=60,
    )
    assert stale["api_integration_active"] is False
    assert stale["feed_fresh"] is False
    original = "<div>FROZEN HIT CARD</div>"
    assert step8f.decorate_card_html(original, _result(1002, 2002), PLAYER_HITS, stale) == original


def test_unproven_freshness_never_exposes_context():
    raw = build_player_prop_api_state(_payload(_prop(1002, 2002, PLAYER_HITS)))
    assert raw["integration_status"] == API_CONNECTED
    assert raw["feed_fresh"] is None
    original = "<div>FROZEN</div>"
    assert step8f.decorate_card_html(original, _result(1002, 2002), PLAYER_HITS, raw) == original


def test_tampered_matching_or_price_input_flags_fail_closed():
    state = _fresh_state()
    original = "<div>FROZEN</div>"
    for key, value in (
        ("player_name_matching_used", True),
        ("fallback_matching_used", True),
        ("fuzzy_matching_allowed", True),
        ("sportsbook_price_model_input", True),
    ):
        tampered = deepcopy(state)
        tampered[key] = value
        assert step8f.decorate_card_html(original, _result(1002, 2002), PLAYER_HITS, tampered) == original


def test_invalid_and_fractional_result_ids_fail_open_without_exception():
    state = _fresh_state()
    original = "<div>FROZEN</div>"
    rows = (
        _result(1002.9, 2002),
        _result(1002, 2002.8),
        _result(True, 2002),
        _result("²", 2002),
    )
    for row in rows:
        assert step8f.decorate_card_html(original, row, PLAYER_HITS, state) == original


def test_ascii_serialized_exact_ids_are_allowed_without_name_matching():
    state = _fresh_state()
    row = _result("1002", "2002", name="Different serialized display")
    html = step8f.decorate_card_html("<div>BASE</div>", row, PLAYER_HITS, state)
    assert "STEP 8F" in html
    assert "EXACT ID MATCH" in html


def test_fallback_transport_state_has_zero_model_and_ranking_impact():
    fallback = step8f._fallback_state("sentinel")
    assert fallback["api_integration_active"] is False
    assert fallback["player_name_matching_used"] is False
    assert fallback["sportsbook_price_model_input"] is False
    for key in (
        "model_math_impact",
        "projection_impact",
        "simulation_impact",
        "probability_impact",
        "line_grading_impact",
        "history_adjustment_impact",
        "ranking_impact",
        "selection_impact",
        "fair_odds_impact",
        "production_exposure_impact",
        "wagering_impact",
        "durable_persistence",
        "wnba_impact",
    ):
        assert fallback[key] is False


def test_installer_patches_only_final_draw_owners_and_is_idempotent(monkeypatch):
    state = _fresh_state()
    fake_st = SimpleNamespace(
        session_state={},
        markdown=lambda *args, **kwargs: None,
        caption=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(step8f, "st", fake_st)
    monkeypatch.setattr(step8f, "_cached_player_prop_api_state", lambda base_url: deepcopy(state))
    monkeypatch.setattr(step8f, "_api_base_url", lambda: "https://example.invalid")

    pitcher = SimpleNamespace()
    pitcher._card_with_headshot = lambda result, rank: "<div>PITCHER BASE</div>"
    pitcher.render_pitcher_k_hub = lambda *args, **kwargs: pitcher._card_with_headshot(_result(1001, 2001), 1)

    hit_active = SimpleNamespace()
    hit_active._pick_html = lambda result, rank: "<div>HIT BASE</div>"
    hits = SimpleNamespace(active=hit_active)
    hits.render_hit_hub = lambda *args, **kwargs: hits.active._pick_html(_result(1002, 2002), 1)

    hrrbi_base = SimpleNamespace()
    hrrbi_base._card = lambda result, rank, threshold: "<div>HRRBI BASE</div>"
    hrrbi = SimpleNamespace(base=hrrbi_base)
    hrrbi.render_hrrbi_hub = lambda *args, **kwargs: hrrbi.base._card(_result(1003, 2003), 1, 2)

    monkeypatch.setitem(sys.modules, "mlb_pitcher_k_hub_v1017", pitcher)
    monkeypatch.setitem(sys.modules, "mlb_hit_hub_v1315", hits)
    monkeypatch.setitem(sys.modules, "mlb_hrrbi_hub_v115", hrrbi)

    first = step8f.install_step8f_player_prop_presentation()
    second = step8f.install_step8f_player_prop_presentation()
    assert first["installed"] is True and second["installed"] is True
    assert first["markets"] == [PITCHER_STRIKEOUTS, PLAYER_HITS, HITS_RUNS_RBI]

    pitcher_html = pitcher.render_pitcher_k_hub(None, None, None, None, None)
    hit_html = hits.render_hit_hub(None, None, None, None, None)
    hrrbi_html = hrrbi.render_hrrbi_hub(None, None, None, None, None)

    for html in (pitcher_html, hit_html, hrrbi_html):
        assert html.count("STEP 8F") == 1
        assert html.count("EXACT ID MATCH") == 1

    assert pitcher_html.count("PITCHER BASE") == 1
    assert hit_html.count("HIT BASE") == 1
    assert hrrbi_html.count("HRRBI BASE") == 1


def test_installed_renderer_with_unavailable_state_returns_original_card(monkeypatch):
    fallback = step8f._fallback_state("offline")
    fake_st = SimpleNamespace(
        session_state={},
        markdown=lambda *args, **kwargs: None,
        caption=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(step8f, "st", fake_st)
    monkeypatch.setattr(step8f, "_cached_player_prop_api_state", lambda base_url: deepcopy(fallback))
    monkeypatch.setattr(step8f, "_api_base_url", lambda: "https://example.invalid")

    pitcher = SimpleNamespace()
    pitcher._card_with_headshot = lambda result, rank: "<div>EXACT FROZEN PITCHER HTML</div>"
    pitcher.render_pitcher_k_hub = lambda *args, **kwargs: pitcher._card_with_headshot(_result(1001, 2001), 1)
    hits = SimpleNamespace(active=SimpleNamespace(_pick_html=lambda result, rank: "<div>HIT</div>"))
    hits.render_hit_hub = lambda *args, **kwargs: hits.active._pick_html(_result(1002, 2002), 1)
    hrrbi = SimpleNamespace(base=SimpleNamespace(_card=lambda result, rank, threshold: "<div>HRRBI</div>"))
    hrrbi.render_hrrbi_hub = lambda *args, **kwargs: hrrbi.base._card(_result(1003, 2003), 1, 2)

    monkeypatch.setitem(sys.modules, "mlb_pitcher_k_hub_v1017", pitcher)
    monkeypatch.setitem(sys.modules, "mlb_hit_hub_v1315", hits)
    monkeypatch.setitem(sys.modules, "mlb_hrrbi_hub_v115", hrrbi)
    step8f.install_step8f_player_prop_presentation()

    assert pitcher.render_pitcher_k_hub(None, None, None, None, None) == "<div>EXACT FROZEN PITCHER HTML</div>"
