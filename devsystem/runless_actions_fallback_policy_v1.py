from __future__ import annotations
import argparse,re
from pathlib import Path
AUTO_RE=re.compile(r"(?m)^\s*(pull_request|pull_request_target|push)\s*:")
def manifest_paths(root):
    p=root/"devsystem/runless_legacy_proof_workflows_v1.txt"
    if not p.exists():raise RuntimeError("RUNLESS_LEGACY_MANIFEST_MISSING")
    return [x.strip() for x in p.read_text().splitlines() if x.strip() and not x.lstrip().startswith("#")]
def audit_legacy_workflows(root):
    bad=[]
    for rel in manifest_paths(root):
        p=root/rel
        if not p.exists():bad.append((rel,"MISSING"));continue
        text=p.read_text()
        if AUTO_RE.search(text):bad.append((rel,"AUTOMATIC_TRIGGER"))
        if "workflow_dispatch" not in text:bad.append((rel,"NO_MANUAL_FALLBACK"))
    return {"green":not bad,"violations":bad}
def main():
    a=argparse.ArgumentParser();a.add_argument("command",choices=["audit"]);a.add_argument("--root",default=".");ns=a.parse_args();r=audit_legacy_workflows(Path(ns.root))
    if r["green"]:print("RUNLESS_ACTIONS_FALLBACK_POLICY_GREEN");return 0
    for x in r["violations"]:print("RUNLESS_ACTIONS_FALLBACK_POLICY_RED",*x)
    return 1
if __name__=="__main__":raise SystemExit(main())
