import pytest
from runless_proof_plane.dry_run import _failclosed_self_tests,DryRunFailure,_exact
def test_failclosed_matrix():
 e=_failclosed_self_tests('a'*40);assert all(e.values())
def test_exact_head_rejects_drift():
 with pytest.raises(DryRunFailure):_exact('a'*40,'b'*40)
