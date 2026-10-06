from datetime import datetime,timezone,timedelta
from runless_proof_plane.fingerprint import *
def fp(dep='d',deploy='x'):return build_fingerprint({'a':'1'},{'d':dep},{'p':1},{'s':1},deploy)
def test_static_reuse_ignores_main_motion_by_construction():assert evaluate_slice_reuse(fp(),fp()).reusable
def test_dependency_drift_invalidates():assert not evaluate_slice_reuse(fp(),fp('e')).reusable
def test_live_identity_and_ttl():
 assert not evaluate_slice_reuse(fp('d','x'),fp('d','y'),live=True,observed_at=datetime.now(timezone.utc)).reusable
 assert not evaluate_slice_reuse(fp(),fp(),live=True,observed_at=datetime.now(timezone.utc)-timedelta(hours=1),ttl_seconds=5).reusable
