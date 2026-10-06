import hashlib,hmac
from fastapi.testclient import TestClient
from runless_proof_plane.api import create_app
from runless_proof_plane.config import Settings

def _full_settings():
 return Settings(bootstrap=False,github_app_id='1',github_app_installation_id='2',github_app_private_key='k',github_webhook_secret='secret')

def _signature(secret,body):
 return 'sha256='+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()

def test_health_contract():
 r=TestClient(create_app(Settings())).get('/health');j=r.json();assert j['status']=='healthy';assert j['service']=='runless-proof-plane';assert j['github_actions_enabled'] is False;assert 'kyre-sports-api' not in str(j)

def test_bootstrap_prove_fails_closed():
 r=TestClient(create_app(Settings())).post('/prove',json={"task_id":"x","workstream":"w","candidate_sha":"a"*40,"lease_id":"l","authorization_id":"a"});assert r.status_code==503

def test_webhook_fails_closed_without_secret():
 s=Settings(bootstrap=False,github_app_id='1',github_app_installation_id='2',github_app_private_key='k');r=TestClient(create_app(s)).post('/github/webhook',content=b'{}');assert r.status_code==503

def test_diagnostics_reuses_shared_client_and_result_cache():
 s=_full_settings();app=create_app(s)
 class StubClient:
  def __init__(self):self.calls=0
  def repository_info(self):self.calls+=1;return {'full_name':s.repository}
 stub=StubClient();app.state.github_client=stub
 c=TestClient(app)
 assert c.get('/diagnostics/github').status_code==200
 assert c.get('/diagnostics/github').status_code==200
 assert stub.calls==1

def test_webhook_replay_rejected_across_requests():
 s=_full_settings();app=create_app(s);body=b'{}';headers={'x-hub-signature-256':_signature('secret',body),'x-github-delivery':'delivery-1'};c=TestClient(app)
 assert c.post('/github/webhook',content=body,headers=headers).status_code==200
 assert c.post('/github/webhook',content=body,headers=headers).status_code==401
