from __future__ import annotations
import hashlib,json,tempfile
from pathlib import Path
from devsystem.runless_proof_plan_v1 import load_plan
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .config import Settings
from .gate import publish_gate
from .github_app import GithubAppAuth
from .github_client import GithubClient
from .models import ProofRequest
from .orchestrator import ProofOrchestrator
from .receipts import GithubReceiptBackend,ReceiptStore
from .registry import RegistryTransaction
from .step2a import Step2ASnapshot,authorize_proof,Step2AError
class DryRunFailure(RuntimeError):pass
def _digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,default=str).encode()).hexdigest()
def _exact(expected,actual):
    if expected!=actual:raise DryRunFailure("RUNLESS_EXACT_HEAD_DRIFT")
def _require_deployment_identity(candidate,deployment_identity):
    if not deployment_identity or len(deployment_identity)!=40 or deployment_identity!=candidate:raise DryRunFailure("RUNLESS_DEPLOYMENT_IDENTITY_MISMATCH")
def _failclosed_self_tests(candidate_sha):
    evidence={}
    try:_exact(candidate_sha,"0"*40);evidence['wrong_sha']=False
    except DryRunFailure:evidence['wrong_sha']=True
    snap=Step2ASnapshot(candidate_sha,"b"*40,1,"h",(),"good","b"*40,"runless")
    req=ProofRequest(task_id='dry',workstream='runless',candidate_sha=candidate_sha,lease_id='stale',authorization_id='a')
    try:authorize_proof(snap,req);evidence['stale_lease']=False
    except Step2AError:evidence['stale_lease']=True
    auth=GithubAppAuth(Settings(github_webhook_secret='dry-run-secret'))
    try:auth.verify_webhook_signature(b'{}','sha256=spoof');evidence['spoofed_webhook']=False
    except ValueError:evidence['spoofed_webhook']=True
    class B:
        def read_registry(self):return {'revision':2,'state_hash':'new','active_thaws':[]}
    try:RegistryTransaction(B()).prepare(expected_revision=1,expected_hash='old',frozen_token='F',merged_sha=candidate_sha);evidence['registry_race']=False
    except RuntimeError:evidence['registry_race']=True
    with tempfile.TemporaryDirectory() as td:
        try:load_plan('missing-plan',Path(td));evidence['missing_plan']=False
        except FileNotFoundError:evidence['missing_plan']=True
    o=ProofOrchestrator();r=ProofRequest(task_id='dry',workstream='runless',candidate_sha=candidate_sha,lease_id='l',authorization_id='a');o.start(r,'p1','same');o.fail('p1','same')
    try:o.start(r,'p2','same');evidence['unchanged_replay']=False
    except RuntimeError:evidence['unchanged_replay']=True
    if not all(evidence.values()):raise DryRunFailure('RUNLESS_FAIL_CLOSED_SELF_TEST_FAILED')
    return evidence
def certify_dry_run(settings:Settings):
    if settings.bootstrap:raise DryRunFailure('RUNLESS_FULL_MODE_REQUIRED')
    candidate=settings.dry_run_candidate
    if not candidate or len(candidate)!=40:raise DryRunFailure('RUNLESS_DRY_RUN_CANDIDATE_REQUIRED')
    _require_deployment_identity(candidate,settings.deployment_identity)
    auth=GithubAppAuth(settings);client=GithubClient(auth,settings.repository)
    repo=client.repository_info();branch_sha=client.branch_sha(settings.source_branch);_exact(candidate,branch_sha);commit=client.commit(candidate)
    evidence=_failclosed_self_tests(candidate);evidence['deployment_identity_match']=True
    evidence['github_auth_read']=repo.get('full_name')==settings.repository and commit.get('sha')==candidate
    if not evidence['github_auth_read']:raise DryRunFailure('RUNLESS_GITHUB_AUTH_DIAGNOSTIC_FAILED')
    proof_id=f"dry-run-{candidate[:16]}";backend=GithubReceiptBackend(client,candidate,settings.receipt_ref,settings.receipt_path);store=ReceiptStore(backend,settings.receipt_ref,settings.receipt_path)
    try:
        receipt=store.get(proof_id);reused=True
    except Exception:
        receipt=build_runless_receipt(proof_id=proof_id,task_id='runless-proof-plane-v1-dry-run',project='API2',workstream='runless-proof-plane-v1',step='dry-run-certification',candidate_sha=candidate,artifact_map={'runless-proof-plane-v1':candidate},dependency_map={'repository':settings.repository},registry_before={'mode':'dry-run-read-only'},registry_after={'mode':'dry-run-read-only'},evidence_digests=[_digest(evidence)],failure_class='NONE',deployment_identity=settings.deployment_identity)
        store.put(receipt);reused=False
    reconstructed=ReceiptStore(GithubReceiptBackend(client,candidate,settings.receipt_ref,settings.receipt_path),settings.receipt_ref,settings.receipt_path).get(proof_id)
    if reconstructed['digest']!=receipt['digest']:raise DryRunFailure('RUNLESS_RESTART_RECONSTRUCTION_FAILED')
    evidence['restart_reconstruction']=True
    publish_gate(client,candidate,'success',receipt,settings.gate_name)
    return {'status':'GREEN','proof_id':proof_id,'candidate_sha':candidate,'gate':settings.gate_name,'receipt_digest':receipt['digest'],'receipt_reused':reused,'fail_closed':evidence,'github_actions_enabled':False}
