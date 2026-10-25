from pathlib import Path

def test_execution_plan_entrypoint_is_api2_native_and_uses_api2_main():
    text=Path("devsystem/api2_execution_plan_compiler_cert_v1.py").read_text().lower(); foreign="mon"+"ster"; assert foreign not in text; assert "execution_plan_compiler_v1" not in text
    from devsystem.api2_execution_plan_compiler_cert_v1 import compile_api2_execution_plan
    plan=compile_api2_execution_plan("a"*40); assert plan["system"]=="api2"; assert plan["authoritative_base_ref"]=="refs/heads/api2-main"; assert plan["failure_recovery_chain"]==["ANTI_LOOP","STEP_2C","STEP_2B","STEP_2A","EXECUTE","VERIFY","GREEN","FROZEN"]


def test_whole_stack_certification_proves_recovery_and_freeze():
    from devsystem.api2_step2bc_cert_v1 import self_test
    result = self_test()
    assert result["status"] == "GREEN"
    assert result["isolation_green"] is True
    assert result["anti_loop_blind_retry_blocked"] is True
    assert result["step2c_autonomous_recovery_green"] is True
    assert result["step2b_fail_closed_green"] is True
    assert result["step2a_one_use_green"] is True
    assert result["green_requires_proof"] is True
    assert result["freeze_readback_green"] is True
    assert result["live_status_complete"] is True
    assert result["proof_registry_green"] is True


def test_authoritative_modules_do_not_import_non_api2_devsystem_authority():
    import ast
    from devsystem.api2_step2bc_cert_v1 import authoritative_module_paths
    for path in authoritative_module_paths():
        tree = ast.parse(Path(path).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("devsystem"):
                assert (node.module or "").startswith("devsystem.api2_")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("devsystem."):
                        assert alias.name.startswith("devsystem.api2_")


def test_authority_manifest_pins_api2_only_refs_and_modules():
    import json
    from devsystem.api2_step2bc_cert_v1 import authoritative_module_paths
    manifest = json.loads(Path("devsystem/api2_authority_manifest_v1.json").read_text())
    assert manifest["system"] == "api2"
    assert manifest["authoritative_base_ref"] == "refs/heads/api2-main"
    assert manifest["proof_ref"] == "refs/heads/api2-proof-registry"
    assert manifest["freeze_ref"] == "refs/heads/api2-frozen-registry"
    assert manifest["foreign_authority_forbidden"] is True
    assert manifest["authority_modules"] == authoritative_module_paths()
