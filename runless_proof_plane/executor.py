from __future__ import annotations
import hashlib,subprocess,time
from pathlib import Path
from devsystem.runless_proof_plan_v1 import validate_command
from .models import FailureClass,SliceEvidence
def _digest(text):return hashlib.sha256(text.encode()).hexdigest()
def execute_command(command,cwd:Path,timeout_seconds:int):
    cmd=list(validate_command(tuple(command)));start=time.monotonic()
    try:
        cp=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout_seconds);fc=FailureClass.NONE if cp.returncode==0 else FailureClass.STATIC_PROOF
        return SliceEvidence(name=" ".join(cmd),ok=cp.returncode==0,command=cmd,stdout_digest=_digest(cp.stdout),stderr_digest=_digest(cp.stderr),duration_seconds=time.monotonic()-start,failure_class=fc)
    except subprocess.TimeoutExpired as e:
        return SliceEvidence(name=" ".join(cmd),ok=False,command=cmd,stdout_digest=_digest((e.stdout or "") if isinstance(e.stdout,str) else ""),stderr_digest=_digest((e.stderr or "") if isinstance(e.stderr,str) else ""),duration_seconds=time.monotonic()-start,failure_class=FailureClass.INFRA)
def execute_static_slice(plan,workspace):return [execute_command(c,workspace.path,plan.timeout_seconds) for c in plan.commands]
