import base64,hashlib,json
from copy import deepcopy
import pytest
from runless_proof_plane.registry import GithubRegistryBackend,RegistryTransaction,freeze_task13

def _hash(payload):
 p=deepcopy(payload);p.pop('state_hash',None);return hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()

def _registry():
 r={'schema_version':1,'version':'MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1','repository':'kyrepeak/kyre-sports-ai','registry_ref':'refs/heads/monster-frozen-artifact-registry','registry_path':'devsystem/frozen_artifact_registry_state_v1.json','revision':7,'source_main_sha':'1'*40,'entries':{'OLD':{'status':'FROZEN','checkpoint_id':'OLD','source_main_sha':'1'*40,'artifacts':{'old.py':'a'*40}}},'active_thaws':[{'thaw_id':'UNRELATED','status':'ACTIVE','target_head_sha':'2'*40,'files':{'old.py':{'from_blob':'a'*40,'to_blob':'b'*40}}}]}
 r['state_hash']=_hash(r);return r

class FakeClient:
 def __init__(self,registry=None):self.registry=registry or _registry();self.blob_sha='c'*40;self.writes=[]
 def content(self,path,ref=None,allow_404=False):
  text=json.dumps(self.registry,indent=2,sort_keys=True)+'\n';return {'sha':self.blob_sha,'encoding':'base64','content':base64.b64encode(text.encode()).decode()}
 def tree_blobs(self,sha):return {'runless_proof_plane/api.py':'d'*40,'docs/runless-proof-plane-operations.md':'e'*40,'tests/test_runless_api.py':'f'*40,'unrelated.py':'9'*40}
 def update_content(self,path,text,branch,message,sha):
  if sha!=self.blob_sha:raise RuntimeError('STALE_BLOB')
  self.registry=json.loads(text);self.blob_sha='8'*40;self.writes.append({'path':path,'branch':branch,'message':message,'sha':sha});return {'content':{'sha':self.blob_sha}}

def test_cas_preserves_unrelated_thaw_and_freezes_selected_surface():
 c=FakeClient();before=deepcopy(c.registry['active_thaws']);b=GithubRegistryBackend(c);t=RegistryTransaction(b);s=b.read_registry();p=t.prepare(expected_revision=s['revision'],expected_hash=s['state_hash'],frozen_token='RUNLESS_PROOF_PLANE_V1_TASK13',merged_sha='3'*40);t.commit(p);rb=t.read_back(p)
 assert rb.revision==8;assert rb.frozen_token=='RUNLESS_PROOF_PLANE_V1_TASK13';assert rb.merged_sha=='3'*40
 assert c.registry['active_thaws']==before
 assert c.registry['entries']['RUNLESS_PROOF_PLANE_V1_TASK13']['artifacts']=={'docs/runless-proof-plane-operations.md':'e'*40,'runless_proof_plane/api.py':'d'*40,'tests/test_runless_api.py':'f'*40}
 assert c.registry['state_hash']==_hash(c.registry);assert len(c.writes)==1

def test_cas_rejects_stale_snapshot_without_write():
 c=FakeClient();b=GithubRegistryBackend(c);s=b.read_registry();c.registry['revision']+=1;c.registry['state_hash']=_hash(c.registry)
 with pytest.raises(RuntimeError,match='WAIT_REGISTRY_RECONCILIATION'):b.cas_freeze(expected_revision=s['revision'],expected_hash=s['state_hash'],frozen_token='RUNLESS_PROOF_PLANE_V1_TASK13',merged_sha='3'*40,preserve_thaws=s['active_thaws'])
 assert c.writes==[]

def test_cas_rejects_conflicting_existing_baseline():
 r=_registry();r['entries']['OTHER']={'status':'FROZEN','checkpoint_id':'OTHER','source_main_sha':'1'*40,'artifacts':{'runless_proof_plane/api.py':'0'*40}};r['state_hash']=_hash(r);c=FakeClient(r);b=GithubRegistryBackend(c);s=b.read_registry()
 with pytest.raises(RuntimeError,match='RUNLESS_FROZEN_BASELINE_CONFLICT'):b.cas_freeze(expected_revision=s['revision'],expected_hash=s['state_hash'],frozen_token='RUNLESS_PROOF_PLANE_V1_TASK13',merged_sha='3'*40,preserve_thaws=s['active_thaws'])
 assert c.writes==[]

def test_freeze_task13_is_single_transaction():
 c=FakeClient();out=freeze_task13(c,'3'*40);assert out['status']=='GREEN';assert out['revision']==8;assert out['merged_sha']=='3'*40;assert len(c.writes)==1
