from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from devsystem import dependency_chain_auto_refresh_v1 as dep


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "devsystem/dependency_chain_registry_v1.json"
WNBA_STEP3 = ROOT / ".github/workflows/wnba-pra-repair-v1-step3-data-completeness.yml"


def test_registry_has_no_static_parent_blob_pin():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    spec = payload["dependencies"]["wnba-pra-repair-v1-step3-step2"]
    assert spec["wake_on_parent_change"] is True
    assert spec["static_parent_blob_pins_forbidden"] is True
    assert "parent_blobs" not in spec
    assert "expected_blob" not in spec


def test_wnba_step3_wakes_on_both_step2_parent_paths():
    text = WNBA_STEP3.read_text(encoding="utf-8")
    for path in (
        "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity.py",
        "wnba_pra_repair_v1_step2_team_identity.py",
    ):
        assert text.count(path) >= 2
        assert f"git hash-object {path}" not in text
    assert "dependency_chain_auto_refresh_v1 verify" in text


def test_old_stale_step2_router_blob_pin_is_gone():
    text = WNBA_STEP3.read_text(encoding="utf-8")
    assert "4e51bd0e0c631b71cf9af7a443038edbe1b7061c" not in text


def test_current_step2_router_identity_is_resolved_dynamically():
    result = dep.build_snapshot(
        "wnba-pra-repair-v1-step3-step2",
        base="HEAD",
        head="HEAD",
    )
    assert result["status"] == "GREEN"
    assert result["decision"] == "DEPENDENCY_CURRENT"
    assert result["static_parent_blob_pin"] is False
    assert result["parent_blobs"][
        "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity.py"
    ] == "3180431d724b26bd7d1129cb0139c81ffdfe49ac"


def test_engine_self_test_is_green():
    result = dep.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["dynamic_parent_identity"] is True
    assert result["parent_change_wakes_child"] is True
    assert result["static_parent_blob_pins_forbidden"] is True


def test_engine_runs_directly():
    completed = subprocess.run(
        [sys.executable, "-m", "devsystem.dependency_chain_auto_refresh_v1", "self-test"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "API2_DEPENDENCY_CHAIN_AUTO_REFRESH_V1_GREEN" in completed.stdout
