from __future__ import annotations
import base64,hashlib,json
from copy import deepcopy
from dataclasses import dataclass
from devsystem.frozen_artifact_registry_v1 import validate_registry

REGISTRY_BRANCH="monster-frozen-artifact-registry"
REGISTRY_REF="refs/heads/monster-frozen-artifact-registry"
REGISTRY_PATH="devsystem/frozen_artifact_registry_state_v1.json"
FINAL_FREEZE_TOKEN="RUNLESS_PROOF_PLANE_V1_TASK13"

def _canonical(payload):return json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True)
def _state_hash(payload):
    value=deepcopy(payload);value.pop("state_hash",None);return hashlib.sha256(_canonical(value).encode()).hexdigest()
def _is_runless_artifact(path):
    return path.startswith("runless_proof_plane/") or path.startswith("devsystem/runless_") or path=="devsystem/task_ledgers/runless-proof-plane-v1-task13.json" or path=="docs/runless-proof-plane-operations.md" or path.startswith("tests/test_runless_") or path.startswith("tests/test_devsystem_runless_")

@dataclass(frozen=True)
class FreezeReadback: revision:int;state_hash:str;frozen_token:str;merged_sha:str

class GithubRegistryBackend:
    def __init__(self,client,branch=REGISTRY_BRANCH,path=REGISTRY_PATH):self.client=client;self.branch=branch;self.path=path;self._blob_sha=None
    def read_registry(self):
        raw=self.client.content(self.path,ref=self.branch)
        if not raw or raw.get("encoding")!="base64":raise RuntimeError("RUNLESS_REGISTRY_READ_FAILED")
        try:text=base64.b64decode(raw["content"]).decode();payload=json.loads(text)
        except Exception as exc:raise RuntimeError("RUNLESS_REGISTRY_DECODE_FAILED") from exc
        validate_registry(payload);self._blob_sha=raw["sha"];return payload
    def _artifacts(self,merged_sha):
        blobs=self.client.tree_blobs(merged_sha);artifacts={p:s for p,s in blobs.items() if _is_runless_artifact(p)}
        if not artifacts:raise RuntimeError("RUNLESS_FREEZE_ARTIFACTS_MISSING")
        return dict(sorted(artifacts.items()))
    def cas_freeze(self,*,expected_revision,expected_hash,frozen_token,merged_sha,preserve_thaws):
        current=self.read_registry()
        if current["revision"]!=expected_revision or current["state_hash"]!=expected_hash:raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")
        if current.get("active_thaws",[])!=preserve_thaws:raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")
        artifacts=self._artifacts(merged_sha)
        thaw_paths={path for grant in current.get("active_thaws",[]) for path in grant.get("files",{})}
        overlap=sorted(set(artifacts)&thaw_paths)
        if overlap:raise RuntimeError("RUNLESS_CONFLICTING_THAW:"+",".join(overlap))
        flattened={}
        for entry in current["entries"].values():flattened.update(entry["artifacts"])
        conflicts=[p for p,blob in artifacts.items() if p in flattened and flattened[p]!=blob]
        if conflicts:raise RuntimeError("RUNLESS_FROZEN_BASELINE_CONFLICT:"+",".join(sorted(conflicts)))
        existing=current["entries"].get(frozen_token)
        if existing:
            if existing.get("source_main_sha")==merged_sha and existing.get("artifacts")==artifacts:return {**current,"frozen_token":frozen_token,"merged_sha":merged_sha}
            raise RuntimeError("RUNLESS_FREEZE_TOKEN_CONFLICT")
        updated=deepcopy(current);updated["revision"]=int(expected_revision)+1;updated["source_main_sha"]=merged_sha;updated["entries"][frozen_token]={"status":"FROZEN","checkpoint_id":frozen_token,"source_main_sha":merged_sha,"artifacts":artifacts};updated["active_thaws"]=deepcopy(preserve_thaws);updated["state_hash"]=_state_hash(updated);validate_registry(updated)
        text=json.dumps(updated,indent=2,sort_keys=True,ensure_ascii=True)+"\n"
        try:self.client.update_content(self.path,text,self.branch,f"registry: freeze {frozen_token}",self._blob_sha)
        except Exception as exc:raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc
        readback=self.read_registry();entry=readback["entries"].get(frozen_token)
        if readback["revision"]!=updated["revision"] or readback["state_hash"]!=updated["state_hash"] or readback.get("active_thaws",[])!=preserve_thaws or not entry or entry.get("source_main_sha")!=merged_sha or entry.get("artifacts")!=artifacts:raise RuntimeError("RUNLESS_REGISTRY_READBACK_MISMATCH")
        return {**readback,"frozen_token":frozen_token,"merged_sha":merged_sha}

class RegistryTransaction:
    def __init__(self,backend):self.backend=backend;self.prepared=None
    def prepare(self,*,expected_revision,expected_hash,frozen_token,merged_sha,unrelated_thaws=()):
        s=self.backend.read_registry()
        if s["revision"]!=expected_revision or s["state_hash"]!=expected_hash:raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")
        self.prepared={"expected_revision":expected_revision,"expected_hash":expected_hash,"frozen_token":frozen_token,"merged_sha":merged_sha,"preserve_thaws":deepcopy(s.get("active_thaws",[]))};return self.prepared
    def commit(self,prepared=None):
        p=prepared or self.prepared
        if not p:raise RuntimeError("RUNLESS_REGISTRY_NOT_PREPARED")
        return self.backend.cas_freeze(**p)
    def read_back(self,expected):
        s=self.backend.read_registry();token=expected["frozen_token"];entry=s.get("entries",{}).get(token)
        frozen_token=token if entry else s.get("frozen_token");merged_sha=entry.get("source_main_sha") if entry else s.get("merged_sha")
        rb=FreezeReadback(s["revision"],s["state_hash"],frozen_token,merged_sha)
        if rb.frozen_token!=token or rb.merged_sha!=expected["merged_sha"]:raise RuntimeError("RUNLESS_REGISTRY_READBACK_MISMATCH")
        return rb

def freeze_task13(client,merged_sha,freeze_token=FINAL_FREEZE_TOKEN):
    backend=GithubRegistryBackend(client);snapshot=backend.read_registry();tx=RegistryTransaction(backend);prepared=tx.prepare(expected_revision=snapshot["revision"],expected_hash=snapshot["state_hash"],frozen_token=freeze_token,merged_sha=merged_sha);committed=tx.commit(prepared);rb=tx.read_back(prepared);return {"status":"GREEN","revision":rb.revision,"state_hash":rb.state_hash,"frozen_token":rb.frozen_token,"merged_sha":rb.merged_sha,"active_thaw_count":len(committed.get("active_thaws",[])),"artifact_count":len(committed["entries"][freeze_token]["artifacts"])}
