import pytest
from devsystem.runless_terminal_proof_receipt_v1 import *
def make():return build_runless_receipt(proof_id='p',task_id='t',project='API2',workstream='w',step='13',candidate_sha='a'*40,artifact_map={'a':'1'},dependency_map={'d':'1'},registry_before={'revision':1},registry_after={'revision':2},evidence_digests=['e'],failure_class='NONE')
def test_receipt_tamper():
 p=make();assert validate_runless_receipt(p);p['step']='x'
 with pytest.raises(ValueError,match='TAMPERED'):validate_runless_receipt(p)
