from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class FreezeReadback: revision:int;state_hash:str;frozen_token:str;merged_sha:str
class RegistryTransaction:
    def __init__(self,backend):self.backend=backend;self.prepared=None
    def prepare(self,*,expected_revision,expected_hash,frozen_token,merged_sha,unrelated_thaws=()):
        s=self.backend.read_registry()
        if s["revision"]!=expected_revision or s["state_hash"]!=expected_hash:raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")
        if any(t.get("conflicts") for t in s.get("active_thaws",[]) if t.get("id") not in set(unrelated_thaws)):raise RuntimeError("RUNLESS_CONFLICTING_THAW")
        self.prepared={"expected_revision":expected_revision,"expected_hash":expected_hash,"frozen_token":frozen_token,"merged_sha":merged_sha,"preserve_thaws":s.get("active_thaws",[])};return self.prepared
    def commit(self,prepared=None):
        p=prepared or self.prepared
        if not p:raise RuntimeError("RUNLESS_REGISTRY_NOT_PREPARED")
        return self.backend.cas_freeze(**p)
    def read_back(self,expected):
        s=self.backend.read_registry();rb=FreezeReadback(s["revision"],s["state_hash"],s["frozen_token"],s["merged_sha"])
        if rb.frozen_token!=expected["frozen_token"] or rb.merged_sha!=expected["merged_sha"]:raise RuntimeError("RUNLESS_REGISTRY_READBACK_MISMATCH")
        return rb
