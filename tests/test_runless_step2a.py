import pytest
from runless_proof_plane.models import ProofRequest
from runless_proof_plane.step2a import build_snapshot,authorize_proof,Step2AError
def req(**kw):
 d=dict(task_id='t',workstream='wnba',candidate_sha='a'*40,lease_id='L',authorization_id='A',expected_main_sha='b'*40);d.update(kw);return ProofRequest(**d)
def reader(_):return dict(candidate_sha='a'*40,main_sha='b'*40,registry_revision=7,registry_hash='h',active_thaws=[],scope_lease='L',rollback_anchor='b'*40,workstream='wnba')
def test_snapshot_and_authorize():assert authorize_proof(build_snapshot(req(),reader),req()).candidate_sha=='a'*40
def test_cross_workstream_rejected():
 s=build_snapshot(req(),reader)
 with pytest.raises(Step2AError):authorize_proof(s,req(workstream='nba'))
def test_github_client_has_no_actions_methods():
 from runless_proof_plane.github_client import GithubClient
 assert not hasattr(GithubClient,'dispatch_workflow') and not hasattr(GithubClient,'rerun_workflow')
 with pytest.raises(ValueError):GithubClient.validate_path('/actions/workflows/1/dispatches')
