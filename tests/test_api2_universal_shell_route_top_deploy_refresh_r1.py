from pathlib import Path

MARKER = "# API 2 Universal Shell Route Top V1 deploy refresh R1 full Streamlit rebuild trigger 2026-10-17"
EXPECTED_DEPENDENCIES = (
    "streamlit",
    "packaging>=20",
    "requests",
    "pypdf",
    "pandas",
    "numpy",
    "streamlit-autorefresh",
    "streamlit-local-storage==0.0.25",
    "tzdata>=2025.2",
    "posthog~=7.48",
)


def test_deploy_refresh_is_comment_only_and_exactly_once():
    text = Path("requirements.txt").read_text()
    assert text.count(MARKER) == 1
    deps = tuple(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    assert deps == EXPECTED_DEPENDENCIES


def test_live_activation_code_remains_successor_runtime():
    app = Path("app.py").read_text()
    assert "API2_UNIVERSAL_SHELL_ROUTE_TOP_V1_RUNTIME" in app
    assert "streamlit_memory_lazy_router_universal_nav_v3" in app
    guard = Path("kyre_universal_entrypoint_cold_start_v1.py").read_text()
    assert "cold" in guard.lower()
