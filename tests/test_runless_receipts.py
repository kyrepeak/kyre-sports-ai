import pytest
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from runless_proof_plane.receipts import ReceiptStore
class B:
 def __init__(self):self.d={}
 def exists(self,p,r):return (r,p) in self.d
 def create_immutable(self,p,c,r):self.d[(r,p)]=c
 def read(self,p,r):return self.d[(r,p)]
def rec(pid='p'):return build_runless_receipt(proof_id=pid,task_id='t',project='API2',workstream='w',step='13',candidate_sha='a'*40,artifact_map={},dependency_map={},registry_before={},registry_after={},evidence_digests=[],failure_class='NONE')
def test_immutable_duplicate_and_restart():
 b=B();s=ReceiptStore(b);s.put(rec());assert s.get('p')['proof_id']=='p';assert ReceiptStore(b).reconstruct('p')[0]['proof_id']=='p'
 with pytest.raises(ValueError):s.put(rec())
