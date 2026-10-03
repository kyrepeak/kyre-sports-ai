from __future__ import annotations

import cfb_game_total_clean_page_v16 as page


def _selector_payload():
    return {
        "requested_date": "2026-09-19",
        "synthetic_ids": False,
        "projection_weight": 0.0,
        "may_modify_projection": False,
        "games": [
            {
                "event_id": "401858999",
                "game_date": "2026-09-19",
                "away_team": "Coastal Carolina",
                "home_team": "Delaware",
                "away_team_id": "324",
                "home_team_id": "48",
                "venue": "Verified Venue",
                "broadcast": "Verified Network",
                "status": "Scheduled",
                "identity_verified": True,
                "identity_source": "server_espn",
            }
        ],
    }


def test_v168_selector_seed_games_use_verified_identity_only(monkeypatch):
    monkeypatch.setattr(
        page.prior_v164,
        "_selector_payload_for_day",
        lambda _day: _selector_payload(),
    )
    games = page._selector_seed_games_v168("2026-09-19")
    assert len(games) == 1
    game = games[0]
    assert game["espn_event_id"] == "401858999"
    assert game["game_id"] == "401858999"
    assert game["away_team"] == "Coastal Carolina"
    assert game["home_team"] == "Delaware"
    assert game["away_espn_team_id"] == "324"
    assert game["home_espn_team_id"] == "48"
    assert game["identity_verified"] is True
    assert game["date_matches_query"] is True
    assert game["schedule_v168_selector_failover"] is True
    assert game["kickoff_et"] == "TBD"
    assert game["kickoff_iso"] == ""


def test_v168_rejects_selector_payload_that_can_modify_projection(monkeypatch):
    payload = _selector_payload()
    payload["projection_weight"] = 0.1
    monkeypatch.setattr(
        page.prior_v164,
        "_selector_payload_for_day",
        lambda _day: payload,
    )
    assert page._selector_seed_games_v168("2026-09-19") == []


def test_v168_schedule_keyerror_switches_to_verified_selector(monkeypatch):
    monkeypatch.setattr(
        page.prior_v164,
        "_selector_payload_for_day",
        lambda _day: _selector_payload(),
    )

    def broken_schedule(_target_date):
        raise KeyError("unexpected live schedule payload")

    games, diag = page._load_schedule_with_selector_failover_v168(
        broken_schedule,
        "2026-09-19",
    )

    assert len(games) == 1
    assert games[0]["espn_event_id"] == "401858999"
    assert diag["schedule_v168_selector_failover_active"] is True
    assert diag["identity_ready"] is True
    assert diag["synthetic_ids"] is False
    assert diag["fuzzy_matching"] is False
    assert diag["projection_weight"] == 0.0
    assert diag["may_modify_projection"] is False
    assert "KeyError" in diag["schedule_v3_failure"]


def test_v168_preserves_healthy_frozen_schedule_path(monkeypatch):
    monkeypatch.setattr(
        page.prior_v164,
        "_selector_payload_for_day",
        lambda _day: (_ for _ in ()).throw(AssertionError("fallback must not run")),
    )
    expected_games = [{"game_id": "ncaa:healthy"}]
    expected_diag = {"source": "NCAA current FBS scoreboard GraphQL"}

    games, diag = page._load_schedule_with_selector_failover_v168(
        lambda _day: (expected_games, expected_diag),
        "2026-09-19",
    )
    assert games is expected_games
    assert diag is expected_diag


def test_v168_render_scopes_schedule_patch_and_restores_frozen_loader(monkeypatch):
    original = page.frozen_schedule.load_with_diagnostics
    observed = {"patched_during_render": False}

    def fake_render(*_args, **_kwargs):
        observed["patched_during_render"] = (
            page.frozen_schedule.load_with_diagnostics is not original
        )
        return "ok"

    monkeypatch.setattr(page.prior_v164, "render_game_total_hub", fake_render)
    result = page.render_game_total_hub()

    assert result == "ok"
    assert observed["patched_during_render"] is True
    assert page.frozen_schedule.load_with_diagnostics is original
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False
    assert (
        page.SCHEDULE_FAILOVER_MARKER
        == "CFB_GAME_TOTAL_V168_SELECTOR_SCHEDULE_FAILOVER_ACTIVE"
    )
