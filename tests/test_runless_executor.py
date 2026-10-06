import pytest
from devsystem.runless_proof_plan_v1 import validate_command
def test_reject_unapproved():
 with pytest.raises(ValueError):validate_command(('bash','-c','echo hi'))
