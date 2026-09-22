from pathlib import Path


WORKFLOWS = {
    ".github/workflows/cfb-runtime-snapshot-refresh.yml": "cfb-runtime-snapshot-auto-refresh-v1",
    ".github/workflows/cfb-runtime-snapshot-refresh-v2.yml": "cfb-runtime-snapshot-auto-refresh-v2",
    ".github/workflows/cfb-market-identity-snapshot-v1.yml": "cfb-market-identity-snapshot-v1",
}


def test_cfb_refresh_workflows_do_not_run_on_every_main_push():
    for path, cert_branch in WORKFLOWS.items():
        text = Path(path).read_text(encoding="utf-8")
        push_block = text.split("schedule:", 1)[0]
        assert "      - main\n" not in push_block, path
        assert f"      - {cert_branch}\n" in push_block, path
        assert "schedule:" in text, path
        assert "workflow_dispatch:" in text, path
        assert "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'" in text, path
        assert "refs/heads/main" not in text.split("runs-on:", 1)[0], path


def test_cfb_identity_safety_contract_remains_visible():
    text = Path(".github/workflows/cfb-market-identity-snapshot-v1.yml").read_text(encoding="utf-8")
    assert "official_event_ids_only" in text
    assert "synthetic_ids" in text
    assert "fuzzy_matching" in text
    assert "sportsbook_projection_weight" in text
    assert "0.0" in text
