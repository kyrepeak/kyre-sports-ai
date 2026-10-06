import pytest
from runless_proof_plane.gate import publish_gate
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
class C:
 def publish_check(self,*a):self.args=a;return a
def rec():return build_runless_receipt(proof_id='p',task_id='t',project='API2',workstream='w',step='13',candidate_sha='a'*40,artifact_map={},dependency_map={},registry_before={},registry_after={},evidence_digests=[],failure_class='NONE')
def test_gate_exact_sha_and_receipt():
 c=C();publish_gate(c,'a'*40,'success',rec());assert c.args[1]=='runless-final-gate'
 with pytest.raises(ValueError):publish_gate(c,'b'*40,'success',rec())
 with pytest.raises(ValueError):publish_gate(c,'a'*40,'success',None)
