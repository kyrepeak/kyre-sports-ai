import pytest
from runless_proof_plane.registry import RegistryTransaction
class B:
 def __init__(self):self.s={'revision':1,'state_hash':'h','active_thaws':[]}
 def read_registry(self):return self.s
 def cas_freeze(self,**p):self.s={'revision':2,'state_hash':'h2','active_thaws':p['preserve_thaws'],'frozen_token':p['frozen_token'],'merged_sha':p['merged_sha']};return self.s
def test_cas_and_readback():
 b=B();t=RegistryTransaction(b);p=t.prepare(expected_revision=1,expected_hash='h',frozen_token='F',merged_sha='a'*40);t.commit(p);assert t.read_back(p).frozen_token=='F'
def test_race_wait():
 b=B();t=RegistryTransaction(b)
 with pytest.raises(RuntimeError,match='WAIT_REGISTRY_RECONCILIATION'):t.prepare(expected_revision=2,expected_hash='h',frozen_token='F',merged_sha='a'*40)
