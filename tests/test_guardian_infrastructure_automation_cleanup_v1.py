from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_retired_render_era_mlb_workflows_are_absent_from_active_tree():
    paths = [
        ".github/workflows/mlb-step18b-production-observability-cert.yml",
        ".github/workflows/mlb-step6b-production-canary-monitor.yml",
        ".github/workflows/mlb-step6d-controlled-25-production-cert.yml",
        ".github/workflows/mlb-step6e-25pct-stability-window.yml",
    ]
    for path in paths:
        assert not (ROOT / path).exists(), path


def test_current_cfb_scheduled_health_workflows_stay_scheduled():
    paths = [
        ".github/workflows/cfb-market-identity-snapshot-v1.yml",
        ".github/workflows/cfb-runtime-snapshot-refresh-v2.yml",
        ".github/workflows/cfb-runtime-snapshot-refresh.yml",
    ]
    for path in paths:
        assert "\n  schedule:" in _text(path)


def test_no_scheduled_workflow_targets_legacy_render_api():
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        if "\n  schedule:" in text:
            assert "kyre-sports-api.onrender.com" not in text
