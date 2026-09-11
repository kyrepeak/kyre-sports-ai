from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "devsystem" / "production_identity_verify_v1.py"
    spec = importlib.util.spec_from_file_location("devsystem_production_identity_verify_v1", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_identity_target_is_pinned_to_certified_render_release():
    module = _load_module()
    targets = module._targets()
    render = targets["render_api"]

    assert render["service_id"] == "srv-da84q6ifngtc73bdbm6g"
    assert render["source_branch"] == "mlb-step17b-shared-host-cert"
    assert render["certified_commit"] == "5de9e2cbff64d1bf28b5835c5fbc9b9484f5e728"
    assert render["auto_deploy"] is False


def test_identity_gate_checks_observed_service_branch_commit_and_observability():
    module = _load_module()
    source = Path(module.__file__).read_text(encoding="utf-8")

    assert 'runtime.get("service_id")' in source
    assert 'runtime.get("deploy_branch")' in source
    assert 'runtime.get("deploy_commit")' in source
    assert 'runtime.get("branch_aligned")' in source
    assert 'payload.get("observability_version")' in source
    assert "Render service ID drift" in source
    assert "Render certified commit drift" in source
