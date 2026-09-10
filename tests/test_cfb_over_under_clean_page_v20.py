"""Regression tests for CFB O/U Clean Page V20 Step 6 activation."""
from __future__ import annotations

import copy
import inspect

import cfb_over_under_clean_page_v20 as page


def _games(event_id="401858213"):
    return [
        {
            "identity_key": f"espn:{event_id}",
            "game_id": event_id,
            "espn_event_id": event_id,
            "away_team": "Florida A&M",
            "home_team": "Miami",
            "kickoff_et": "7:30 PM ET",
        }
    ]


def _payload(event_id="401858213", total=55.5):
    return {
        "step": 3,
        "schema_version": "cfb_odds_v1",
        "captured_at_utc": "2026-09-10T14:30:00+00:00",
        "source": "test",
        "game_count": 1,
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
        "games": [
            {
                "game_id": event_id,
                "provider_game_id": "fd-test",
                "game_date": "2026-09-10",
                "away_team": "Florida A&M",
                "home_team": "Miami",
                "sportsbook": "FanDuel",
                "market_type": "game_total",
                "total": total,
                "line_status": "active",
                "line_updated_at_utc": "2026-09-10T14:30:00+00:00",
                "identity_verified": True,
            }
        ],
    }


def test_v20_is_additive_over_certified_v19_and_v2():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v19"
    assert page.ACTIVE_MARKET_ADAPTER == "cfb_over_under_market_adapter_v2"
    assert page.ACTIVE_MARKET_INTELLIGENCE == "cfb_over_under_market_intelligence_v1"
    assert page.frozen_page.MODEL_VERSION.startswith("CFB O/U CLEAN PAGE V19")
    assert page.market_adapter_v2.MODEL_VERSION.startswith("CFB O/U MARKET ADAPTER V2")


def test_v20_activates_single_book_context_by_exact_official_espn_id_only():
    games = _games()
    payload = _payload()
    games_before = copy.deepcopy(games)
    payload_before = copy.deepcopy(payload)

    attached, diag = page.attach_market_lines(games, payload)

    assert games == games_before
    assert payload == payload_before
    assert diag["matching_method"] == "official ESPN event_id only"
    assert diag["fuzzy_matching"] is False
    assert diag["synthetic_ids"] is False
    assert diag["market_intelligence_status"] == "LIVE"
    assert diag["market_intelligence_games"] == 1
    assert diag["projection_weight"] == 0.0
    assert diag["market_context_only"] is True
    assert diag["may_modify_projection"] is False

    row = attached[0]
    assert row["market_official_game_id"] == row["espn_event_id"] == "401858213"
    intelligence = row["market_intelligence"]
    assert intelligence["game_id"] == "401858213"
    assert intelligence["provider_count"] == 1
    assert intelligence["market_state"] == "SINGLE_BOOK"
    assert intelligence["consensus_available"] is False
    assert intelligence["projection_weight"] == 0.0
    assert intelligence["market_context_only"] is True
    assert intelligence["may_modify_projection"] is False


def test_v20_does_not_cross_attach_market_intelligence_to_wrong_event_id():
    attached, diag = page.attach_market_lines(_games("401858214"), _payload("401858213"))
    row = attached[0]
    assert row["market_line_available"] is False
    assert "market_intelligence" not in row
    assert row["market_intelligence_status"] == "UNAVAILABLE"
    assert diag["market_intelligence_games"] == 0


def test_v20_fail_closes_intelligence_on_nonzero_market_weight():
    payload = _payload()
    payload["market_semantics"]["projection_weight"] = 0.01

    attached, diag = page.attach_market_lines(_games(), payload)

    assert attached[0]["market_line_available"] is True
    assert "market_intelligence" not in attached[0]
    assert attached[0]["market_intelligence_status"] == "UNAVAILABLE"
    assert diag["market_intelligence_status"] == "UNAVAILABLE"
    assert "unsafe_nonzero_projection_weight" in diag["market_intelligence_error"]
    assert diag["projection_weight"] == 0.0


def test_v20_single_book_caption_never_claims_consensus():
    attached, _ = page.attach_market_lines(_games(), _payload())
    html = page._market_caption(attached[0], {"status": "GREEN"})

    assert "STEP 5C MARKET INTELLIGENCE LIVE" in html
    assert "SINGLE-BOOK CONTEXT" in html
    assert "CONSENSUS" not in html
    assert "ESPN event 401858213" in html
    assert "projection influence <b>0.0%</b>" in html


def test_v20_market_intelligence_failure_is_visible_and_projection_safe():
    game = _games()[0]
    game.update(
        {
            "market_line_available": True,
            "market_identity_verified": True,
            "market_official_game_id": "401858213",
            "market_total": 55.5,
            "market_sportsbook": "FanDuel",
            "market_status": "active",
            "market_updated_at_utc": "2026-09-10T14:30:00+00:00",
            "market_projection_weight": 0.0,
            "market_intelligence_status": "UNAVAILABLE",
        }
    )
    html = page._market_caption(game, {"status": "GREEN"})
    assert "MARKET INTELLIGENCE UNAVAILABLE" in html
    assert "fail-closed" in html
    assert "projection influence remains <b>0.0%</b>" in html


def test_v20_replaces_only_active_page_marker(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    proxy = page._StreamlitV20Proxy()
    proxy.caption(
        "🟢 CFB O/U • CLEAN PAGE V19 ACTIVE • FRESHNESS FIREWALL ACTIVE • "
        "FROZEN PROJECTION MATH PRESERVED"
    )
    proxy.caption("ordinary downstream caption")

    assert "CLEAN PAGE V20 ACTIVE" in seen[0]
    assert "MARKET INTELLIGENCE LIVE" in seen[0]
    assert "0.0% PROJECTION INFLUENCE" in seen[0]
    assert seen[1] == "ordinary downstream caption"


def test_v20_render_reuses_v19_body_and_changes_only_presentation_globals():
    assert page._RENDER_V20.__code__ is page.frozen_page._RENDER_V19.__code__
    assert page._RENDER_V20.__globals__["market_adapter"] is page._market_adapter_facade
    assert page._RENDER_V20.__globals__["_market_caption"] is page._market_caption
    assert page._RENDER_V20.__globals__["_line_board"] is page._line_board


def test_v20_contains_no_projection_engine_call_or_schedule_reimplementation():
    source = inspect.getsource(page)
    assert "runtime_slate.analyze_game(" not in source
    assert "final_model" not in source
    assert "project_matchup(" not in source
    assert "apply_to_raw(" not in source
    assert "schedule_v5" not in source
    assert "schedule_v6" not in source
