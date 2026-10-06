import pytest
from devsystem.runless_proof_plan_v1 import validate_command,load_plan
def test_allowlist_and_shell_rejection():
 assert validate_command(('python','-m','pytest','-q','x.py'));assert validate_command(('python','-m','devsystem.cert'))
 with pytest.raises(ValueError):validate_command(('python','-m','pytest','x.py;','curl','x'))
def test_missing_plan_fails_closed(tmp_path):
 with pytest.raises(FileNotFoundError,match='RUNLESS_PLAN_REQUIRED'):load_plan('missing',tmp_path)
