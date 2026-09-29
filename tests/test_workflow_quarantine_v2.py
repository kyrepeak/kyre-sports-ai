from __future__ import annotations

import json
from pathlib import Path

from devsystem.workflow_quarantine_v2 import _on_block, validate


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "devsystem/workflow_quarantine_v2.json"


def test_registry_is_frozen_and_exact():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert data["status"] == "FROZEN"
    assert len(data["workflows"]) == 16
    assert data["baseline"]["pull_request_automatic"] == 16
    assert data["baseline"]["push_automatic"] == 12
    assert data["baseline"]["manual_only_after"] == 16


def test_every_quarantined_workflow_is_manual_only_and_intact():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for entry in data["workflows"]:
        source = (ROOT / entry["path"]).read_text(encoding="utf-8")
        block = _on_block(source)
        assert "workflow_dispatch:" in block, entry["path"]
        assert "pull_request:" not in block, entry["path"]
        assert "push:" not in block, entry["path"]
        assert "schedule:" not in block, entry["path"]
        assert "jobs:" in source, entry["path"]


def test_real_validator_green():
    result = validate(ROOT)
    assert result["status"] == "GREEN"
    assert result["quarantined_workflows"] == 16
    assert result["automatic_triggers_after"] == 0
    assert result["manual_dispatch_preserved"] == 16
