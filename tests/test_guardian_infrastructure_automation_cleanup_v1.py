from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_active_guardian_monitors_do_not_reference_legacy_render_or_dead_streamlit_root():
    paths = [
        ".github/workflows/mlb-step6b-production-canary-monitor.yml",
        ".github/workflows/mlb-step6d-controlled-25-production-cert.yml",
    ]
    for path in paths:
        text = _text(path)
        assert "kyre-sports-api.onrender.com" not in text
        assert "https://kyre-sports-ai.streamlit.app" not in text


def test_step6d_handles_undersized_percentage_cohort_semantically():
    text = _text(".github/workflows/mlb-step6d-controlled-25-production-cert.yml")
    assert "INSUFFICIENT_SLATE_FOR_PERCENT_CANARY" in text
    assert "STEP6D_25_PERCENT_ACTIVATION_NOT_RESOLVED" in text


def test_step6b_does_not_require_retired_streamlit_transport():
    text = _text(".github/workflows/mlb-step6b-production-canary-monitor.yml")
    assert "STEP6B_STREAMLIT_ROOT" not in text
    assert "STEP6B_STREAMLIT_STATUS" not in text
