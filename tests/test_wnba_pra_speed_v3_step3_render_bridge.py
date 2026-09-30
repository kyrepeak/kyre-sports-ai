from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "sports_api" / "api" / "wnba_pra_detail_bundle.py"
MAIN = ROOT / "sports_api" / "main.py"


def test_render_bridge_uses_exact_step3_route_contract():
    source = ROUTE.read_text(encoding="utf-8")
    assert '@router.get("/players/{player_id}/pra-detail")' in source
    assert '"streamlit_hosted_reads_required": 1' in source
    assert "build_step18a_consumer_latest" in source
    assert "get_player_game_log_dataset" in source
    assert '"projection_run": False' in source
    assert '"sportsbook_network_called": False' in source


def test_render_host_registers_only_step3_route_seam():
    source = MAIN.read_text(encoding="utf-8")
    assert "from sports_api.api.wnba_pra_detail_bundle import router as wnba_pra_detail_bundle_router" in source
    assert "app.include_router(wnba_pra_detail_bundle_router)" in source


def test_render_bridge_workflow_has_guarded_manual_deploy_and_rollback():
    workflow = (ROOT / ".github" / "workflows" / "wnba-pra-speed-v3-step3-render-bridge.yml").read_text(encoding="utf-8")
    assert "push:" in workflow
    assert "mlb-step17b-shared-host-cert" in workflow
    assert "deploy-render:" in workflow
    assert "RENDER_API_KEY" in workflow
    assert "WNBA_STEP17B_EXPECTED_REVISION" in workflow
    assert "WNBA_DEPLOYMENT_REVISION" in workflow
    assert "WNBA_RELEASE_ID" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP3_RENDER_DEPLOY_GREEN" in workflow
    assert "rollback" in workflow.lower()
