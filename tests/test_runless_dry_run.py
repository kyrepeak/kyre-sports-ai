import pytest
from runless_proof_plane.dry_run import _failclosed_self_tests,DryRunFailure,_exact,_require_deployment_identity

def test_failclosed_matrix():
 e=_failclosed_self_tests('a'*40);assert all(e.values())

def test_exact_head_rejects_drift():
 with pytest.raises(DryRunFailure):_exact('a'*40,'b'*40)

def test_deployment_identity_must_match_candidate():
 candidate='a'*40
 _require_deployment_identity(candidate,candidate)
 with pytest.raises(DryRunFailure,match='RUNLESS_DEPLOYMENT_IDENTITY_MISMATCH'):_require_deployment_identity(candidate,'b'*40)
 with pytest.raises(DryRunFailure,match='RUNLESS_DEPLOYMENT_IDENTITY_MISMATCH'):_require_deployment_identity(candidate,None)
