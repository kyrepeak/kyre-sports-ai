from __future__ import annotations

import inspect

from devsystem import production_verify_page_cleanup_step6 as verifier


def test_step6_verifier_targets_exact_cleanup_contract():
    assert verifier.CERT_DATE == "2026-09-19"
    assert verifier.CERT_EVENT_ID == "401858458"
    assert verifier.CERT_MATCHUP == "Purdue @ UCLA"
    assert "STEP2_PRESENTATION_ACTIVE" in verifier.STEP2_MARKER
    assert "STEP4_TEAM_EVIDENCE_UI_ACTIVE" in verifier.STEP4_MARKER


def test_step6_verifier_is_passive_stable_session():
    source = inspect.getsource(verifier.verify)
    waiter = inspect.getsource(verifier._wait_for_cleanup_surface)
    combined = source + waiter
    assert "page.reload" not in combined
    assert "reload(" not in combined
    assert "restart" not in combined.lower()
    assert "clear_cache" not in combined
    assert '"/~/+/?"' in source
    assert "page.wait_for_timeout(2000)" in waiter


def test_step6_verifier_requires_all_cleanup_surfaces():
    hero = inspect.getsource(verifier._assert_hero)
    teams = inspect.getsource(verifier._assert_team_evidence)
    game = inspect.getsource(verifier._assert_game_evidence)
    assert "expected_check = f\"{ready_value}/{total_value} Data Check\"" in hero
    assert "ready_metrics.count() != 4" in hero
    assert 'state != "READY"' not in hero
    assert "0.0% sportsbook projection influence" in hero
    assert "ready_cards.count() != 2" in teams
    assert "ready_stats.count() != 8" in teams
    assert "Rose Bowl" in game
    assert '"unavailable" in lowered' in game
    assert "Scheduled" in game


def test_step6_verifier_does_not_modify_projection_or_product():
    source = inspect.getsource(verifier)
    assert "sportsbook_projection_influence" in source
    assert '"projection_mutation": False' in source
    assert "streamlit_memory_lazy_router" not in source
    assert "cfb_game_total_clean_page" not in source


def test_step6_checked_in_runtime_snapshot_contains_exact_purdue_ucla_event():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "data" / "cfb_runtime_snapshot_v2.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        row for row in payload.get("games", [])
        if str(row.get("event_id") or "") == "401858458"
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["away_team"] == "Purdue"
    assert row["home_team"] == "UCLA"
    assert row["venue"] == "Rose Bowl"
    assert len(row["away"]["completed_games"]) == 2
    assert len(row["home"]["completed_games"]) == 2
    assert row["away"]["ppg"] == 40
    assert row["away"]["points_allowed_pg"] == 28.5
    assert row["home"]["ppg"] == 36.5
    assert row["home"]["points_allowed_pg"] == 17


def test_step6_environment_adapter_prefers_checked_in_exact_event_cache(monkeypatch):
    import cfb_game_total_game_evidence_v1 as evidence

    def fail_network(*_args, **_kwargs):
        raise AssertionError("network fallback must not run when verified cache exists")

    monkeypatch.setattr(evidence.environment_owner, "_fetch_summary", fail_network)
    monkeypatch.setattr(evidence.environment_owner, "_fetch_scoreboard", fail_network)

    payload, diag = evidence._environment_payload({
        "espn_event_id": "401858458",
        "game_date": "2026-09-19",
        "away_team": "Purdue",
        "home_team": "UCLA",
    })
    assert diag["cache_used"] is True
    assert payload["venue"]["name"] == "Rose Bowl"
    assert payload["venue"]["city"] == "Pasadena"
    assert payload["weather"]["temperature_f"] == 73.0
    assert payload["weather"]["gust_mph"] == 5.0
    assert payload["weather"]["precipitation_pct"] == 0.0
    assert payload["kickoff"] == "2026-09-19T23:00:00-04:00"
    assert payload["status"] == "Scheduled"
