import pytest
from runless_proof_plane.models import ProofRequest,ProofState
from runless_proof_plane.orchestrator import ProofOrchestrator,ORDER
def req(w='w'):return ProofRequest(task_id='t',workstream=w,candidate_sha='a'*40,lease_id='l',authorization_id='a')
def test_legal_chain_to_green_frozen():
 o=ProofOrchestrator();o.start(req(),'p','f')
 for state in ORDER[1:]:o.advance('p',state)
 assert o.status('p').state==ProofState.GREEN_FROZEN
def test_illegal_skip_and_loop_block():
 o=ProofOrchestrator();o.start(req(),'p','f')
 with pytest.raises(RuntimeError):o.advance('p',ProofState.FINGERPRINT)
 o.fail('p','f')
 with pytest.raises(RuntimeError,match='UNCHANGED'):o.start(req(),'p2','f')
