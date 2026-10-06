from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requirements.txt"
APP = ROOT / "app.py"
CERT = ROOT / "devsystem" / "wnba_pra_repair_v1_step8_runtime_recovery_cert.py"

MARKER = "# WNBA PRA Repair V1 Step 8 runtime recovery full Streamlit redeploy trigger 2026-10-06 R1"
PACKAGE_LINES = (
    "streamlit",
    "requests",
    "pandas",
    "numpy",
    "streamlit-autorefresh",
    "streamlit-local-storage==0.0.25",
    "tzdata>=2025.2",
    "posthog~=7.48",
)


def test_step8_full_redeploy_marker_exists_once_without_dependency_changes():
    lines = REQ.read_text(encoding="utf-8").splitlines()
    assert lines[: len(PACKAGE_LINES)] == list(PACKAGE_LINES)
    assert lines.count(MARKER) == 1


def test_step8_keeps_step7_runtime_active_and_does_not_patch_product_logic():
    app = APP.read_text(encoding="utf-8")
    assert "WNBA_PRA_REPAIR_V1_STEP7_FINAL_INTEGRATION_RUNTIME" in app
    assert (
        "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration "
        "import record_bootstrap_import_ms, render_app"
    ) in app


def test_step8_certifier_exists_and_is_deployment_only():
    assert CERT.exists(), "Step 8 runtime-recovery cert does not exist yet"
    source = CERT.read_text(encoding="utf-8")
    for token in (
        'PRODUCT_RUNTIME_CHANGED = False',
        'ROUTER_CHANGED = False',
        'MODEL_MATH_CHANGED = False',
        'PROJECTION_MATH_CHANGED = False',
        'MARKET_MATH_CHANGED = False',
        'PROBABILITY_MATH_CHANGED = False',
        'DATA_MEANING_CHANGED = False',
        'PAST_GAMES_ALLOWED = False',
        'FULL_REDEPLOY_MARKER = MARKER',
    ):
        assert token in source


def test_step8_certifier_requires_future_pregame_and_step7_public_runtime():
    assert CERT.exists(), "Step 8 runtime-recovery cert does not exist yet"
    source = CERT.read_text(encoding="utf-8")
    assert "_future_pregame_dates" in source
    assert "_prime_wnba_pra_route" in source
    assert "WNBA_PRA_REPAIR_V1_STEP7_FINAL_INTEGRATION" in source
    assert "scheduled future WNBA pregame" in source


def test_step8_public_prime_accepts_off_day_slate_before_future_date_selection():
    source = CERT.read_text(encoding="utf-8")
    assert "WNBA_PRA_REPAIR_V1_STEP8_OFF_DAY_SLATE_ACCEPTED_GREEN" in source
    assert "Step-8 WNBA/PRA slate did not become route-ready" in source
    assert '"WNBA Slate" in body' in source
    assert '"Slate date" in body' in source
    assert "from devsystem.wnba_pra_speed_v3_step9_final_cert import _prime_wnba_pra_route" not in source
