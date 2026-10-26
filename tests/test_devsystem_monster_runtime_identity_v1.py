from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "devsystem" / "monster_runtime_identity_v1.py"
APP = ROOT / "app.py"


def _load():
    assert MODULE.is_file(), "MONSTER runtime identity module is required"
    spec = importlib.util.spec_from_file_location("monster_runtime_identity_v1", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_identity_is_monster_owned_and_exact():
    mod = _load()
    identity = mod.build_runtime_identity(
        sha="1" * 40,
        tree_sha="2" * 40,
        deployment_id="monster-streamlit-" + "1" * 12,
    )
    assert identity["owner"] == "MONSTER"
    assert identity["sha"] == "1" * 40
    assert identity["deployment_id"] == "monster-streamlit-" + "1" * 12
    assert identity["entrypoint"] == "app.py"
    assert identity["router_owner"] == "MONSTER_CANONICAL_ROUTER"
    assert identity["schema_version"] == "MONSTER_STEP2G_RUNTIME_IDENTITY_V1"
    assert len(identity["artifact_digest"]) == 64


def test_marker_round_trips_identity_without_visible_ui_copy():
    mod = _load()
    identity = mod.build_runtime_identity(
        sha="3" * 40,
        tree_sha="4" * 40,
        deployment_id="monster-streamlit-" + "3" * 12,
    )
    html = mod.runtime_identity_marker_html(identity)
    assert 'id="monster-runtime-identity"' in html
    payload = html.split('data-monster-runtime-identity="', 1)[1].split('"', 1)[0]
    decoded = json.loads(mod.unescape_marker_payload(payload))
    assert decoded == identity
    assert "display:none" in html.replace(" ", "")


def test_app_uses_runtime_identity_and_has_no_legacy_heartbeat_constant():
    text = APP.read_text(encoding="utf-8")
    assert "emit_runtime_identity_marker" in text
    assert "_STREAMLIT_DEPLOYMENT_HEARTBEAT" not in text
