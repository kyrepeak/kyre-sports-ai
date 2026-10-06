from pathlib import Path
import inspect,pytest
from runless_proof_plane import github_client
from devsystem.runless_proof_plan_v1 import load_plan
from runless_proof_plane.registry import RegistryTransaction
ROOT=Path(__file__).parents[1]
def test_no_actions_dispatch_rerun_api_paths():
 src=inspect.getsource(github_client);assert 'RUNLESS_ACTIONS_API_FORBIDDEN' in src;assert not hasattr(github_client.GithubClient,'rerun_workflow') and not hasattr(github_client.GithubClient,'dispatch_workflow')
def test_missing_plan_fails_closed(tmp_path):
 with pytest.raises(FileNotFoundError):load_plan('missing',tmp_path)
def test_manual_fallback_rule_documented():
 t=(ROOT/'docs/runless-proof-plane-operations.md').read_text();assert 'explicit Kyre authorization' in t;assert 'must not depend on GitHub Actions' in t
def test_green_frozen_requires_readback_contract():
 assert 'READBACK_MISMATCH' in inspect.getsource(RegistryTransaction.read_back)
