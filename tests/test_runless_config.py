import pytest
from runless_proof_plane.config import Settings
def test_defaults_and_bootstrap():
 s=Settings.from_env({});assert s.repository=="kyrepeak/kyre-sports-ai";assert s.receipt_ref=="runless-proof-receipts";assert s.gate_name=="runless-final-gate";assert s.bootstrap
def test_nonbootstrap_fails_closed_without_secrets():
 with pytest.raises(RuntimeError,match="RUNLESS_SECRETS_REQUIRED"):Settings.from_env({"RPP_FULL_APP_ENABLED":"1"})
