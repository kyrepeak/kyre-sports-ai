from __future__ import annotations

from pathlib import Path

import cfb_game_total_clean_page_v15 as page_v164
import cfb_game_total_team_logo_identity_v1 as logo_identity
import cfb_over_under_logo_resolver_v3 as frozen_logo

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v15.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v160.py"
APP = ROOT / "app.py"


def _read(path: Path) -> str:
    assert path.exists(), f"missing required V164 file: {path.name}"
    return path.read_text(encoding="utf-8")


def test_v164_selector_payload_supplies_exact_espn_team_ids_without_name_guessing():
    game = {
        "espn_event_id": "401869940",
        "game_date": "2026-09-19",
        "away_team": "Coastal Carolina",
        "home_team": "Delaware",
    }
    payload = {
        "games": [
            {
                "event_id": "401869940",
                "away_team_id": "324",
                "home_team_id": "48",
                "away_team": "Coastal Carolina",
                "home_team": "Delaware",
            }
        ]
    }
    enriched = logo_identity.enrich_exact_team_ids(game, payload)
    assert enriched["away_espn_team_id"] == "324"
    assert enriched["home_espn_team_id"] == "48"
    assert enriched["logo_identity_source"] == "ESPN exact event_id -> exact team IDs"



def test_v164_uses_kyre_api_exact_ids_before_direct_espn_fallback(monkeypatch):
    game = {
        "espn_event_id": "401869940",
        "game_date": "2026-09-19",
        "away_team": "Coastal Carolina",
        "home_team": "Delaware",
    }
    monkeypatch.setattr(
        logo_identity,
        "_api_rows",
        lambda _day: (
            {
                "event_id": "401869940",
                "away_team_id": "324",
                "home_team_id": "48",
            },
        ),
    )
    monkeypatch.setattr(
        logo_identity,
        "_espn_rows",
        lambda _day: (_ for _ in ()).throw(AssertionError("direct ESPN fallback should not run")),
    )
    enriched = logo_identity.enrich_exact_team_ids(game, {"games": []})
    assert enriched["away_espn_team_id"] == "324"
    assert enriched["home_espn_team_id"] == "48"


def test_v164_team_identity_endpoint_is_additive_and_projection_neutral():
    source = _read(ROOT / "cfb_game_total_team_logo_identity_v1.py")
    assert 'TEAM_IDENTITY_ENDPOINT = "/api/v1/cfb/identity/team-logos"' in source
    assert "_api_rows" in source
    assert "projection_weight" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source

def test_v164_exact_ids_resolve_to_official_espn_logo_cdn():
    game = {
        "away_espn_team_id": "324",
        "home_espn_team_id": "48",
    }
    visuals = frozen_logo.resolve_visuals(game)
    assert visuals["away"]["logo"].endswith("/324.png")
    assert visuals["home"]["logo"].endswith("/48.png")
    assert visuals["away"]["exact_identity"] is True
    assert visuals["home"]["exact_identity"] is True


def test_v164_fails_closed_without_exact_event_identity():
    game = {
        "game_date": "2026-09-19",
        "away_team": "Coastal Carolina",
        "home_team": "Delaware",
    }
    payload = {
        "games": [
            {
                "event_id": "different-event",
                "away_team_id": "324",
                "home_team_id": "48",
            }
        ]
    }
    enriched = logo_identity.enrich_exact_team_ids(game, payload)
    assert "away_espn_team_id" not in enriched
    assert "home_espn_team_id" not in enriched


def test_v164_page_is_additive_over_frozen_v163():
    source = _read(PAGE)
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v14"' in source
    assert "cfb_game_total_team_logo_identity_v1" in source
    assert "_FROZEN_RESOLVE_VISUALS" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v164_router_advances_only_game_total_page():
    source = _read(ROUTER)
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v159"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v15"' in source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V164_PRODUCTION_ACTIVE"' in source
    assert 'STEP1_PROFILE_HEARTBEAT = "CFB_GAME_TOTAL_STEP1_EXACT_EVENT_PROFILE_HANDOFF_ACTIVE"' in source
    assert 'LEGACY_V163_HEARTBEAT = "CFB_GAME_TOTAL_V163_PRODUCTION_ACTIVE"' in source
    assert "return prior._render_cfb_game_total_v159(market)" in source
    assert "return prior.render_app()" in source


def test_app_activates_router_v160():
    source = _read(APP)
    assert "from streamlit_memory_lazy_router_v160 import record_bootstrap_import_ms, render_app" in source


def test_v164_display_reconcile_enriches_exact_team_ids_before_frozen_logo_resolution(monkeypatch):
    def frozen_reconcile(game, selected_day, frozen_away, frozen_home):
        return (
            {
                "espn_event_id": "401869940",
                "game_date": "2026-09-19",
                "away_team": "Coastal Carolina",
                "home_team": "Delaware",
            },
            dict(frozen_away),
            dict(frozen_home),
            {"runtime_status": "GREEN"},
        )

    monkeypatch.setattr(
        page_v164,
        "_FROZEN_RECONCILE_DISPLAY_BUNDLE",
        frozen_reconcile,
    )
    monkeypatch.setattr(
        page_v164,
        "_selector_payload_for_day",
        lambda selected_day: {
            "games": [
                {
                    "event_id": "401869940",
                    "away_team_id": "324",
                    "home_team_id": "48",
                    "identity_verified": True,
                }
            ]
        },
    )

    display_game, away, home, diag = page_v164._reconcile_display_bundle_v164(
        {"espn_event_id": "401869940"},
        "2026-09-19",
        {"team": "Coastal Carolina"},
        {"team": "Delaware"},
    )
    assert display_game["away_espn_team_id"] == "324"
    assert display_game["home_espn_team_id"] == "48"
    assert diag["v164_logo_team_ids_enriched"] is True

    visuals = frozen_logo.resolve_visuals(display_game)
    assert visuals["away"]["logo"].endswith("/324.png")
    assert visuals["home"]["logo"].endswith("/48.png")


def test_v164_per_team_identity_hook_injects_exact_api_logo(monkeypatch):
    monkeypatch.setattr(
        logo_identity,
        "_api_rows",
        lambda _day: (
            {
                "event_id": "401869940",
                "away_team_id": "324",
                "home_team_id": "48",
            },
        ),
    )
    monkeypatch.setattr(
        logo_identity,
        "_espn_rows",
        lambda _day: (_ for _ in ()).throw(
            AssertionError("direct ESPN fallback should not run")
        ),
    )

    away = page_v164._team_identity_v164(
        {
            "espn_event_id": "401869940",
            "game_date": "2026-09-19",
            "away_team": "Coastal Carolina",
            "home_team": "Delaware",
        },
        {"team": "Coastal Carolina", "conference": "Sun Belt"},
        {},
        "away",
    )
    home = page_v164._team_identity_v164(
        {
            "espn_event_id": "401869940",
            "game_date": "2026-09-19",
            "away_team": "Coastal Carolina",
            "home_team": "Delaware",
        },
        {"team": "Delaware", "conference": "CUSA"},
        {},
        "home",
    )
    assert away["exact_identity"] is True
    assert home["exact_identity"] is True
    assert away["team_id"] == "324"
    assert home["team_id"] == "48"
    assert away["logo"].endswith("/324.png")
    assert home["logo"].endswith("/48.png")


def test_v164_render_monkeypatches_only_per_team_identity_temporarily():
    source = _read(PAGE)
    assert "identity_owner._team_identity = _team_identity_v164" in source
    assert "identity_owner._team_identity = original_team_identity" in source
    assert "identity_owner._identity_state =" not in source


def test_v164_per_team_hook_uses_certified_selector_ids_before_network_fallback(monkeypatch):
    monkeypatch.setattr(
        page_v164,
        "_selector_payload_for_day",
        lambda _day: {
            "games": [
                {
                    "event_id": "401869940",
                    "away_team_id": "324",
                    "home_team_id": "48",
                    "identity_verified": True,
                }
            ],
            "synthetic_ids": False,
            "projection_weight": 0.0,
            "may_modify_projection": False,
        },
    )
    monkeypatch.setattr(
        logo_identity,
        "_api_rows",
        lambda _day: (_ for _ in ()).throw(
            AssertionError("secondary API fallback should not run")
        ),
    )
    monkeypatch.setattr(
        logo_identity,
        "_espn_rows",
        lambda _day: (_ for _ in ()).throw(
            AssertionError("direct ESPN fallback should not run")
        ),
    )

    away = page_v164._team_identity_v164(
        {
            "espn_event_id": "401869940",
            "game_date": "2026-09-19",
            "away_team": "Coastal Carolina",
            "home_team": "Delaware",
        },
        {"team": "Coastal Carolina", "conference": "Sun Belt"},
        {},
        "away",
    )
    home = page_v164._team_identity_v164(
        {
            "espn_event_id": "401869940",
            "game_date": "2026-09-19",
            "away_team": "Coastal Carolina",
            "home_team": "Delaware",
        },
        {"team": "Delaware", "conference": "CUSA"},
        {},
        "home",
    )

    assert away["team_id"] == "324"
    assert home["team_id"] == "48"
    assert away["logo"].endswith("/324.png")
    assert home["logo"].endswith("/48.png")


def test_v164_blank_ncaa_event_placeholder_uses_exact_query_event_for_logos(monkeypatch):
    """Regression: NCAA creates espn_event_id='' before optional ESPN enrichment."""
    monkeypatch.setattr(
        page_v164.prior_v163,
        "_query_event_id",
        lambda: "401869940",
    )
    monkeypatch.setattr(
        page_v164,
        "_selector_payload_for_day",
        lambda selected_day: {
            "games": [
                {
                    "event_id": "401869940",
                    "away_team_id": "324",
                    "home_team_id": "48",
                    "identity_verified": True,
                }
            ],
            "synthetic_ids": False,
            "projection_weight": 0.0,
            "may_modify_projection": False,
        },
    )
    monkeypatch.setattr(
        logo_identity,
        "_api_rows",
        lambda _day: (_ for _ in ()).throw(
            AssertionError("selector IDs should resolve before secondary API fallback")
        ),
    )
    monkeypatch.setattr(
        logo_identity,
        "_espn_rows",
        lambda _day: (_ for _ in ()).throw(
            AssertionError("direct ESPN fallback should not run")
        ),
    )

    game = {
        "game_id": "NCAA-PLACEHOLDER-ID",
        "espn_event_id": "",
        "game_date": "2026-09-19",
        "away_team": "Coastal Carolina",
        "home_team": "Delaware",
    }
    away = page_v164._team_identity_v164(
        game,
        {"team": "Coastal Carolina", "conference": "Sun Belt"},
        {},
        "away",
    )
    home = page_v164._team_identity_v164(
        game,
        {"team": "Delaware", "conference": "CUSA"},
        {},
        "home",
    )

    assert away["exact_identity"] is True
    assert home["exact_identity"] is True
    assert away["team_id"] == "324"
    assert home["team_id"] == "48"
    assert away["logo"].endswith("/324.png")
    assert home["logo"].endswith("/48.png")



def test_v164_router_emits_step1_profile_marker_before_page_import():
    source = _read(ROUTER)
    marker_index = source.index("STEP1_PROFILE_HEARTBEAT")
    render_index = source.index("_render_production_heartbeat()")
    import_index = source.index("page = root._import(ACTIVE_PAGE)")
    assert marker_index < import_index
    assert render_index < import_index
    assert "{STEP1_PROFILE_HEARTBEAT}" in source


def test_v164_hidden_identity_marker_renders_without_runtime_name_error(monkeypatch):
    rendered = []
    monkeypatch.setattr(
        page_v164.st,
        "markdown",
        lambda html, **kwargs: rendered.append(str(html)),
    )
    page_v164._render_v164_identity()
    assert len(rendered) == 1
    body = rendered[0]
    assert page_v164.DEPLOYMENT_PROOF_MARKER in body
    assert page_v164.STEP1_PRESENTATION_MARKER in body
    assert page_v164.STEP1_PROFILE_MARKER in body
    assert page_v164.STEP2_PRESENTATION_MARKER in body
    assert page_v164.STEP3_PRESENTATION_MARKER in body
    assert page_v164.STEP4_PRESENTATION_MARKER in body


def test_v164_deployment_marker_renders_before_frozen_hub_handoff():
    source = _read(PAGE)
    marker_call = source.index("    _render_v164_identity()")
    frozen_call = source.index("        result = prior_v163.render_game_total_hub")
    assert marker_call < frozen_call



def test_v164_step2_uses_rich_verified_evidence_and_step1_exact_profile():
    source = _read(PAGE)
    assert 'rendered_identity["away_stats"] = dict(away or {})' in source
    assert 'rendered_identity["home_stats"] = dict(home or {})' in source
    assert 'rendered_identity["step1_away"] = dict(step_away)' in source
    assert 'rendered_identity["step1_home"] = dict(step_home)' in source
    assert "step2_away = _merge_step2_evidence(" in source
    assert "step2_home = _merge_step2_evidence(" in source
    assert 'rendered_identity.get("away_stats") or {}' in source
    assert 'rendered_identity.get("step1_away") or {}' in source
    assert "step2_away," in source
    assert "step2_home," in source



def test_v164_step3_is_connected_after_frozen_steps_1_and_2():
    source = _read(PAGE)
    assert "import cfb_game_total_step3_form_v1 as step3_owner" in source
    assert "STEP3_PRESENTATION_MARKER = step3_owner.STEP3_PRESENTATION_MARKER" in source
    assert "if int(number) == 3:" in source
    assert "step3_owner.render_step3_html(" in source
    assert "rendered_identity.get(\"step2_away\") or {}" in source
    assert "rendered_identity.get(\"step2_home\") or {}" in source
    assert "step1_owner.STEP1_CSS + step2_owner.STEP2_CSS + step3_owner.STEP3_CSS" in source



def test_v164_step3_uses_rich_verified_completed_game_evidence():
    source = _read(PAGE)
    assert "import cfb_game_total_step3_form_v1 as step3_owner" in source
    assert "STEP3_PRESENTATION_MARKER = step3_owner.STEP3_PRESENTATION_MARKER" in source
    assert "if int(number) == 3:" in source
    assert "step3_away = _merge_step2_evidence(" in source
    assert "step3_home = _merge_step2_evidence(" in source
    assert "step3_owner.render_step3_html(" in source
    assert "step3_owner.STEP3_CSS" in source



def test_v164_step3_uses_certified_team_data_foundation_before_render():
    source = _read(PAGE)
    assert "import cfb_team_data_v1 as step3_data_owner" in source
    assert "def _step3_certified_foundation(display_game):" in source
    assert "step3_data_owner.load_matchup_team_data(" in source
    assert "step3_foundation_away, step3_foundation_home = _step3_certified_foundation(" in source
    assert "step3_foundation_away," in source
    assert "step3_foundation_home," in source



def test_v164_step3_certified_foundation_is_reachable_and_unique():
    source = _read(PAGE)
    assert source.count("if int(number) == 3:") == 1
    step3_block = source[source.index("if int(number) == 3:"):source.index("return original_step_evidence")]
    assert "_step3_certified_foundation(" in step3_block
    assert "step3_foundation_away" in step3_block
    assert "step3_foundation_home" in step3_block
    assert 'rendered_identity.get("step2_away") or {}' in step3_block
    assert 'rendered_identity.get("step2_home") or {}' in step3_block
    assert "step3_owner.render_step3_html(" in step3_block



def test_v164_step3_runs_exact_id_live_fallback_after_certified_foundation():
    source = _read(PAGE)
    step3_block = source[source.index("if int(number) == 3:"):source.index("return original_step_evidence")]
    assert "_step3_certified_foundation(" in step3_block
    assert "step3_owner.enrich_step3_inputs(" in step3_block
    assert 'step3_game["espn_event_id"] = event_id' in step3_block
    assert "logo_identity.enrich_exact_team_ids(" in step3_block
    assert "step3_owner.render_step3_html(" in step3_block



def test_v164_step4_is_connected_after_frozen_steps_1_to_3():
    source = _read(PAGE)
    assert "import cfb_game_total_step4_matchup_v1 as step4_owner" in source
    assert "STEP4_PRESENTATION_MARKER = step4_owner.STEP4_PRESENTATION_MARKER" in source
    assert "if int(number) == 4:" in source
    assert "step4_owner.render_step4_html(" in source
    assert 'rendered_identity.get("step3_away") or {}' in source
    assert 'rendered_identity.get("step3_home") or {}' in source
    assert "step1_owner.STEP1_CSS + step2_owner.STEP2_CSS + step3_owner.STEP3_CSS + step4_owner.STEP4_CSS" in source



def test_v164_step3_replaces_blank_game_date_before_hydration():
    source = _read(PAGE)
    step3_block = source[source.index("if int(number) == 3:"):source.index("if int(number) == 4:")]
    assert 'if selected_day and not str(step3_game.get("game_date") or "").strip():' in step3_block
    assert 'step3_game["game_date"] = selected_day' in step3_block
    assert 'step3_game.setdefault("game_date", selected_day)' not in step3_block
    assert "step3_owner.enrich_step3_inputs(" in step3_block



def test_v164_step3_embeds_live_hydration_diagnostics_for_production_proof():
    source = _read(PAGE)
    step3_block = source[source.index("if int(number) == 3:"):source.index("if int(number) == 4:")]
    assert "step3_diag = step3_owner.enrich_step3_inputs" in step3_block
    assert 'rendered_identity["step3_diag"]' in step3_block
    assert '"scoreboard_range_rows"' in step3_block
    assert '"scoreboard_quality_universe"' in step3_block
    assert '"away_espn_team_id"' in step3_block
    assert 'data-step3-diag=' in step3_block


def test_v164_step2_uses_runtime_v2_foundation_and_drive_snapshot_adapter():
    source = PAGE.read_text(encoding="utf-8")
    assert "import cfb_game_total_step2_drive_v1 as step2_drive_owner" in source
    assert "def _step2_certified_foundation(" in source
    foundation_start = source.index("def _step2_certified_foundation(")
    foundation_end = source.index("def step_evidence_v164(", foundation_start)
    foundation = source[foundation_start:foundation_end]
    assert "step3_owner._runtime_v2_step3_bundle(" in foundation
    assert 'merged["record"] = runtime_record' in foundation
    assert 'merged["record_text"] = runtime_record' in foundation

    start = source.index("if int(number) == 2:")
    end = source.index("if int(number) == 3:", start)
    block = source[start:end]
    assert "_step2_certified_foundation(" in block
    assert "step2_drive_owner.enrich_step2_drive_metrics(" in block
    assert block.index("_step2_certified_foundation(") < block.index(
        "step2_drive_owner.enrich_step2_drive_metrics("
    )
