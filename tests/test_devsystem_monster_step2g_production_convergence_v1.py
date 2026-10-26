from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
IDENTITY = ROOT / "devsystem" / "monster_runtime_identity_v1.py"
PROBE = ROOT / "devsystem" / "monster_step2g_production_live_probe_v1.py"


def _load(name: str, path: Path):
    assert path.is_file(), f"missing required MONSTER production file: {path.relative_to(ROOT)}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_main_app_additively_emits_monster_runtime_identity_after_render():
    text = APP.read_text(encoding="utf-8")
    assert "from devsystem.monster_runtime_identity_v1 import emit_runtime_identity_marker" in text
    assert "render_app()" in text
    assert "emit_runtime_identity_marker()" in text
    assert text.index("render_app()") < text.index("emit_runtime_identity_marker()")
    # Shared production markers remain untouched; MONSTER is additive only.
    assert "_STREAMLIT_DEPLOYMENT_HEARTBEAT" in text
    assert "_STEP2G_DEPLOYMENT_MARKER" in text


def test_monster_runtime_identity_is_self_owned_and_exact_sha_tree_bound():
    mod = _load("monster_runtime_identity_v1_prod", IDENTITY)
    identity = mod.build_runtime_identity(
        sha="1" * 40,
        tree_sha="2" * 40,
        deployment_id="monster-streamlit-prod",
    )
    assert identity["owner"] == "MONSTER"
    assert identity["sha"] == "1" * 40
    assert identity["tree_sha"] == "2" * 40
    assert identity["entrypoint"] == "app.py"
    assert identity["router_owner"] == "MONSTER_CANONICAL_ROUTER"
    assert len(identity["artifact_digest"]) == 64


def test_production_probe_requires_exact_main_sha_tree_and_monster_owner():
    mod = _load("monster_step2g_production_live_probe_v1", PROBE)
    expected = mod.expected_identity("3" * 40, "4" * 40)
    assert expected["owner"] == "MONSTER"
    assert expected["sha"] == "3" * 40
    assert expected["tree_sha"] == "4" * 40
    assert expected["schema_version"] == "MONSTER_STEP2G_RUNTIME_IDENTITY_V1"


def test_production_files_do_not_import_monster_main_or_foreign_proof_state():
    for path in (IDENTITY, PROBE):
        text = path.read_text(encoding="utf-8").lower()
        assert "api2" not in text
        assert "monster-main" not in text
        assert "frozen_registry" not in text
        assert "finalization_ledger" not in text
