import pytest

def _reliability_payload(root_digest="a"*64):
    return {"system":"api2","acceptance_criteria":["fix parser","prove regression"],"authoritative_path":{"problem_id":"api2-p1","branch":"api2-fix-r1","proof_path":"api2-proof-r1"},"root_cause":{"finding":"configuration precedence bug","evidence_digest":root_digest},"requirement_to_implementation":{"fix parser":["devsystem/api2_parser.py"],"prove regression":["tests/test_api2_parser.py"]},"requirement_to_proof":{"fix parser":["test_parser_fix"],"prove regression":["test_regression"]},"production_dependencies":[{"name":"python","verified":True}],"provider_reachability":[{"name":"provider","relevant":True,"verified":True}],"configuration_assumptions":[{"name":"API_URL","verified":True}],"regression_risks":[{"risk":"old parser path","proof":"test_regression"}],"verification":["pytest tests/test_api2_parser.py"],"repair_delta":{"prior_repair":"change parser","new_repair":"fix env precedence before parser","new_evidence_digest":"b"*64,"materially_different":True}}

def test_isolation_rejects_foreign_authority_reference():
    from devsystem.api2_isolation_guard_v1 import IsolationViolation, validate_api2_authority
    foreign=("mon"+"ster")+"-live-branch"
    with pytest.raises(IsolationViolation): validate_api2_authority({"system":"api2","authoritative_branch":foreign})
def test_isolation_accepts_api2_authority():
    from devsystem.api2_isolation_guard_v1 import validate_api2_authority
    assert validate_api2_authority({"system":"api2","problem_id":"api2-problem-1","authoritative_branch":"api2-fix-r1","base_ref":"refs/heads/api2-main"})["system"]=="api2"
def test_anti_loop_blocks_blind_repeat_and_allows_new_evidence_plus_hypothesis():
    from devsystem.api2_anti_loop_v1 import record_failure, authorize_retry
    state=record_failure({},action={"type":"PATCH","target":"api2.py"},evidence=["test A failed"],hypothesis="parser bug")
    assert authorize_retry(state,action={"type":"PATCH","target":"api2.py"},evidence=["test A failed"],hypothesis="parser bug")["allowed"] is False
    assert authorize_retry(state,action={"type":"PATCH","target":"api2.py"},evidence=["runtime trace shows stale config"],hypothesis="configuration precedence bug")["allowed"] is True
def test_step2c_selects_deepest_supported_root_cause_and_keeps_technical_failure_autonomous():
    from devsystem.api2_step2c_root_cause_v1 import investigate
    probes=[{"domain":"runtime","depth":1,"supported":True,"finding":"endpoint 500","evidence":"HTTP 500"},{"domain":"tests","depth":1,"supported":True,"finding":"integration red","evidence":"test output"},{"domain":"configuration","depth":3,"supported":True,"finding":"wrong env precedence","evidence":"resolved URL stale"},{"domain":"dependency","depth":2,"supported":True,"finding":"dependency healthy","evidence":"health 200"}]
    result=investigate(failure={"class":"RUNTIME","failed_action":"deploy"},probes=probes); assert result["root_cause"]=="wrong env precedence"; assert result["human_only_blocker"] is False; assert result["next_phase"]=="STEP_2B"
def test_step2c_does_not_advance_until_relevant_domains_are_observed():
    from devsystem.api2_step2c_root_cause_v1 import investigate
    result=investigate(failure={"class":"DEPLOYMENT","failed_action":"deploy"},probes=[{"domain":"runtime","depth":3,"supported":True,"finding":"bad env","evidence":"trace"}]); assert result["next_phase"]=="STEP_2C"; assert "deployment" in result["missing_domains"]
def test_step2c_human_only_blocker_is_narrow():
    from devsystem.api2_step2c_root_cause_v1 import classify_human_only_blocker
    assert classify_human_only_blocker({"kind":"missing_user_credentials"}) is True; assert classify_human_only_blocker({"kind":"test_failure"}) is False; assert classify_human_only_blocker({"kind":"provider_timeout"}) is False
def test_step2b_requires_complete_evidence_and_material_delta():
    from devsystem.api2_step2b_reliability_gate_v1 import validate_repair
    assert validate_repair(_reliability_payload())["allowed"] is True
    bad=_reliability_payload(); bad["requirement_to_proof"].pop("prove regression"); assert validate_repair(bad)["allowed"] is False
    bad2=_reliability_payload(); bad2["repair_delta"]["materially_different"]=False; assert validate_repair(bad2)["allowed"] is False
def test_step2a_enforces_single_problem_path_and_one_use_authorization():
    from devsystem.api2_step2a_authority_v1 import begin_problem, authorize_repair, consume_authorization, Step2AError
    state=begin_problem({},problem_id="api2-p1",branch="api2-fix-r1",proof_path="api2-proof-r1")
    with pytest.raises(Step2AError): begin_problem(state,problem_id="api2-p2",branch="api2-fix-r2",proof_path="api2-proof-r2")
    rel={"allowed":True,"decision_digest":"c"*64}; auth=authorize_repair(state,repair={"type":"PATCH","target":"x.py"},reliability=rel,anti_loop={"allowed":True,"decision":"EVIDENCE_BACKED_RETRY"}); state2=consume_authorization(state,auth)
    with pytest.raises(Step2AError): consume_authorization(state2,auth)
def test_controller_requires_2c_2b_2a_after_failure_and_reports_live_status():
    from devsystem.api2_execution_controller_v2 import new_state, record_failure, submit_step2c, submit_step2b, authorize_repair, status_snapshot
    from devsystem.api2_step2c_root_cause_v1 import investigate
    state=new_state(problem_id="api2-p1",branch="api2-fix-r1",proof_path="api2-proof-r1",acceptance_criteria=["fix parser","prove regression"]); state=record_failure(state,action={"type":"PATCH","target":"x.py"},evidence=["red test"],hypothesis="symptom")
    assert status_snapshot(state)["step_2c_status"]=="REQUIRED"
    inv=investigate(failure={"class":"RUNTIME"},probes=[{"domain":"runtime","depth":1,"supported":True,"finding":"500","evidence":"500"},{"domain":"tests","depth":1,"supported":True,"finding":"red","evidence":"red"},{"domain":"configuration","depth":3,"supported":True,"finding":"config bug","evidence":"trace"},{"domain":"dependency","depth":1,"supported":True,"finding":"healthy","evidence":"200"}]); state=submit_step2c(state,inv); rel=_reliability_payload(inv["evidence_digest"]); state=submit_step2b(state,rel); state,token=authorize_repair(state,{"type":"PATCH","target":"x.py"}); snap=status_snapshot(state); assert token["system"]=="api2"; assert snap["step_2a_authorization_status"]=="AUTHORIZED"; assert snap["anti_loop_status"]=="SATISFIED"
def test_controller_cannot_verify_before_authorized_execution_is_consumed():
    from devsystem.api2_execution_controller_v2 import new_state, record_verification, ControllerError
    state=new_state(problem_id="api2-p1",branch="api2-fix-r1",proof_path="api2-proof-r1",acceptance_criteria=["a"])
    with pytest.raises(ControllerError,match="OUT_OF_ORDER"): record_verification(state,{"a":True})
def test_green_requires_all_acceptance_proof_and_freeze_is_separate():
    from devsystem.api2_execution_controller_v2 import new_state, record_failure, submit_step2c, submit_step2b, authorize_repair, mark_repair_executed, record_verification, ControllerError
    from devsystem.api2_step2c_root_cause_v1 import investigate
    state=new_state(problem_id="api2-p1",branch="api2-fix-r1",proof_path="api2-proof-r1",acceptance_criteria=["a","b"]); state=record_failure(state,action={"type":"PATCH","target":"x.py"},evidence=["red"],hypothesis="symptom")
    inv=investigate(failure={"class":"RUNTIME"},probes=[{"domain":"runtime","depth":1,"supported":True,"finding":"500","evidence":"500"},{"domain":"tests","depth":1,"supported":True,"finding":"red","evidence":"red"},{"domain":"configuration","depth":3,"supported":True,"finding":"config bug","evidence":"trace"},{"domain":"dependency","depth":1,"supported":True,"finding":"healthy","evidence":"200"}]); state=submit_step2c(state,inv); rel=_reliability_payload(inv["evidence_digest"]); rel["acceptance_criteria"]=["a","b"]; rel["requirement_to_implementation"]={"a":["x.py"],"b":["y.py"]}; rel["requirement_to_proof"]={"a":["ta"],"b":["tb"]}; state=submit_step2b(state,rel); state,auth=authorize_repair(state,{"type":"PATCH","target":"x.py"}); state=mark_repair_executed(state,auth)
    with pytest.raises(ControllerError): record_verification(state,{"a":True})
    green=record_verification(state,{"a":True,"b":True}); assert green["green"] is True and green["frozen"] is False
def test_api2_freeze_registry_binds_exact_artifacts_and_evidence():
    from devsystem.api2_frozen_registry_v1 import new_registry,freeze_checkpoint,verify_checkpoint
    reg=freeze_checkpoint(new_registry(),checkpoint_id="API2_STEP2BC_V1_FROZEN",candidate_sha="1"*40,merged_sha="2"*40,evidence_digest="3"*64,artifacts={"devsystem/api2_execution_controller_v2.py":"4"*40}); assert verify_checkpoint(reg,"API2_STEP2BC_V1_FROZEN")["status"]=="FROZEN"
def test_controller_freeze_requires_api2_registry_readback():
    from devsystem.api2_execution_controller_v2 import record_freeze_readback, ControllerError
    with pytest.raises(ControllerError): record_freeze_readback({"system":"api2","green":False,"phase":"VERIFY"},{"status":"FROZEN"})
    frozen=record_freeze_readback({"system":"api2","green":True,"phase":"GREEN"},{"status":"FROZEN","checkpoint_id":"API2_X_FROZEN"}); assert frozen["frozen"] is True and frozen["phase"]=="FROZEN"
