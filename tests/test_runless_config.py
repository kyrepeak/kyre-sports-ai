import pytest
from runless_proof_plane.config import Settings
def test_defaults_and_bootstrap():
 s=Settings.from_env({});assert s.repository=="kyrepeak/kyre-sports-ai";assert s.receipt_ref=="runless-proof-receipts";assert s.gate_name=="runless-final-gate";assert s.bootstrap;assert not s.final_freeze_on_start;assert s.freeze_token=="RUNLESS_PROOF_PLANE_V1_TASK13"
def test_nonbootstrap_fails_closed_without_secrets():
 with pytest.raises(RuntimeError,match="RUNLESS_SECRETS_REQUIRED"):Settings.from_env({"RPP_FULL_APP_ENABLED":"1"})
def test_final_freeze_flag_from_env():
 s=Settings.from_env({"RPP_FINAL_FREEZE_ON_START":"1"});assert s.final_freeze_on_start is True
