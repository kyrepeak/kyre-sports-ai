from devsystem.runless_actions_fallback_policy_v1 import audit_legacy_workflows
def test_policy_accepts_manual_only(tmp_path):
 (tmp_path/'devsystem').mkdir();(tmp_path/'.github/workflows').mkdir(parents=True);(tmp_path/'devsystem/runless_legacy_proof_workflows_v1.txt').write_text('.github/workflows/a.yml\n');(tmp_path/'.github/workflows/a.yml').write_text('on:\n  workflow_dispatch:\n');assert audit_legacy_workflows(tmp_path)['green']
def test_policy_rejects_pr_trigger(tmp_path):
 (tmp_path/'devsystem').mkdir();(tmp_path/'.github/workflows').mkdir(parents=True);(tmp_path/'devsystem/runless_legacy_proof_workflows_v1.txt').write_text('.github/workflows/a.yml\n');(tmp_path/'.github/workflows/a.yml').write_text('on:\n  pull_request:\n  workflow_dispatch:\n');assert not audit_legacy_workflows(tmp_path)['green']
