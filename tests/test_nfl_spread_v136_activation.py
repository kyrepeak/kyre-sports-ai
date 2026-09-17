from __future__ import annotations

import ast
from pathlib import Path


APP = Path("app.py")
ROOT = Path(__file__).resolve().parents[1]


def _string_assignments() -> dict[str, str]:
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    values: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            value = ast.literal_eval(node.value)
        except Exception:
            continue
        if isinstance(value, str):
            values[target.id] = value
    return values


def test_app_preserves_v136_identity_under_additive_successor_bootstrap() -> None:
    source = APP.read_text(encoding="utf-8")
    values = _string_assignments()

    assert values["FROZEN_V134_DEPLOYMENT_HEARTBEAT"] == (
        "STREAMLIT_MAIN_V134_NFL_SPREAD_MODEL_MC_2026-09-14"
    )
    assert values["FROZEN_V135_DEPLOYMENT_HEARTBEAT"] == (
        "STREAMLIT_MAIN_V135_NFL_SPREAD_VISUAL_PARITY_2026-09-14"
    )
    assert values["DEPLOYMENT_HEARTBEAT"] == (
        "STREAMLIT_MAIN_V136_NFL_SPREAD_FRESH_ROUTER_2026-09-14"
    )

    active_v136 = (
        "from streamlit_memory_lazy_router_v136 import "
        "record_bootstrap_import_ms, render_app"
    )
    active_v157 = (
        "from streamlit_memory_lazy_router_v157 import "
        "record_bootstrap_import_ms, render_app"
    )
    stale_active_v135 = (
        "from streamlit_memory_lazy_router_v135 import "
        "record_bootstrap_import_ms, render_app"
    )

    if source.count(active_v136) == 1:
        assert stale_active_v135 not in source
        return

    assert source.count(active_v157) == 1
    v157_source = (ROOT / "streamlit_memory_lazy_router_v157.py").read_text(encoding="utf-8")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v156"' in v157_source
    assert "import streamlit_memory_lazy_router_v156 as prior" in v157_source
    assert stale_active_v135 not in source


def test_v136_activation_does_not_mutate_frozen_v135_identity() -> None:
    source = APP.read_text(encoding="utf-8")

    assert (
        'FROZEN_V135_DEPLOYMENT_HEARTBEAT = '
        '"STREAMLIT_MAIN_V135_NFL_SPREAD_VISUAL_PARITY_2026-09-14"'
    ) in source
    assert (
        'DEPLOYMENT_HEARTBEAT = '
        '"STREAMLIT_MAIN_V136_NFL_SPREAD_FRESH_ROUTER_2026-09-14"'
    ) in source
