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
    assert "12/12 Data Check" in hero
    assert "ready_metrics.count() != 4" in hero
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


def _purdue_ucla_game():
    return {
        "game_id": "6604119",
        "identity_key": "ncaa:6604119",
        "game_date": "2026-09-19",
        "kickoff_iso": "2026-09-19T23:00:00-04:00",
        "away_team": "Purdue",
        "home_team": "UCLA",
        "espn_event_id": "401858458",
        "away_team_id": "2509",
        "home_team_id": "26",
        "identity_verified": True,
        "date_matches_query": True,
        "status": "Scheduled",
    }


def test_step6_model_input_v2_is_exact_local_and_model_ready():
    import cfb_game_total_model_input_v2 as model_input

    profiles, diag = model_input.local_exact_profiles(
        _purdue_ucla_game(), "2026-09-19"
    )
    assert diag["ready"] is True
    assert diag["event_id"] == "401858458"
    assert diag["source"] == "checked-in-certified-runtime-v2"
    assert profiles["away"]["ppg"] == 40.0
    assert profiles["away"]["points_allowed_pg"] == 28.5
    assert profiles["home"]["ppg"] == 36.5
    assert profiles["home"]["points_allowed_pg"] == 17.0
    assert profiles["away"]["data_quality"]["grade"] != "CHECK"
    assert profiles["home"]["data_quality"]["grade"] != "CHECK"


def test_step6_slate_v3_bypasses_external_team_data_for_exact_local_event(monkeypatch):
    import cfb_game_total_slate_v3 as slate

    def fail_external(*_args, **_kwargs):
        raise AssertionError("external team-data path must be bypassed")

    slate.clear_scan_cache()
    monkeypatch.setattr(slate.team_data, "load_matchup_team_data", fail_external)
    result = slate.analyze_game(_purdue_ucla_game(), "2026-09-19")
    assert result["raw"]["ready"] is True, result["raw"].get("reasons")
    assert float(result["raw"]["projected_combined_total"]) > 0
    assert result["final"]["ready"] is True, result["final"].get("reasons")
    assert float(result["final"]["projected_combined_total"]) > 0
    assert result["final"]["forecast_strength"] is not None
    assert result["team_diag"]["external_team_data_bypassed"] is True
    assert slate.raw_model is slate.frozen.raw_model
    assert slate.final_model is slate.frozen.final_model


def test_step6_game_evidence_v2_uses_local_cache_without_network(monkeypatch):
    import cfb_game_total_game_evidence_v1 as prior_evidence
    import cfb_game_total_game_evidence_v2 as evidence

    def fail_network(*_args, **_kwargs):
        raise AssertionError("network must not run for cached exact event")

    monkeypatch.setattr(prior_evidence.environment_owner, "_fetch_summary", fail_network)
    monkeypatch.setattr(prior_evidence.environment_owner, "_fetch_scoreboard", fail_network)
    display, diag = evidence.enrich_game_evidence(
        {"venue": "Venue unavailable", "status": "Scheduled", "kickoff_iso": "2026-09-19T23:00:00-04:00"},
        _purdue_ucla_game(),
    )
    assert diag["cache_used"] is True
    assert diag["data_green"] is True
    assert display["venue"] == "Rose Bowl"
    assert display["temperature"] == 73.0
    assert display["weather"] == "0% precipitation"
    assert display["wind"] == "5 mph gusts"


def test_step6_page_v25_injects_only_fresh_helpers_and_restores():
    import cfb_game_total_clean_page_v25 as page
    import cfb_game_total_game_evidence_v2 as evidence_v2
    import cfb_game_total_slate_v3 as slate_v3

    original_slate = page.slate_hook_owner.slate_v2
    original_evidence = page.prior.game_evidence
    seen = {}

    def callback():
        seen["slate"] = page.slate_hook_owner.slate_v2
        seen["evidence"] = page.prior.game_evidence
        return "ok"

    assert page._render_with_runtime_fresh_helpers(callback) == "ok"
    assert seen["slate"] is slate_v3
    assert seen["evidence"] is evidence_v2
    assert page.slate_hook_owner.slate_v2 is original_slate
    assert page.prior.game_evidence is original_evidence


def test_step6_router_v170_and_app_boot_fresh_page():
    from pathlib import Path
    import streamlit_memory_lazy_router_v170 as router

    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v25"
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v170 import record_bootstrap_import_ms, render_app" in source
    assert "from streamlit_memory_lazy_router_v169 import record_bootstrap_import_ms, render_app" in source
