from fastapi.testclient import TestClient
from runless_proof_plane.api import create_app
from runless_proof_plane.config import Settings
def test_health_contract():
 r=TestClient(create_app(Settings())).get('/health');j=r.json();assert j['status']=='healthy';assert j['service']=='runless-proof-plane';assert j['github_actions_enabled'] is False;assert 'kyre-sports-api' not in str(j)
def test_bootstrap_prove_fails_closed():
 r=TestClient(create_app(Settings())).post('/prove',json={"task_id":"x","workstream":"w","candidate_sha":"a"*40,"lease_id":"l","authorization_id":"a"});assert r.status_code==503
def test_webhook_fails_closed_without_secret():
 s=Settings(bootstrap=False,github_app_id='1',github_app_installation_id='2',github_app_private_key='k');r=TestClient(create_app(s)).post('/github/webhook',content=b'{}');assert r.status_code==503
