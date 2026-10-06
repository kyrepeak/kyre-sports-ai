from __future__ import annotations
import json,re
from dataclasses import dataclass
from pathlib import Path
BAD_SHELL=re.compile(r"[;&|><`$\n\r]");APPROVED_MODULE_PREFIXES=("devsystem.",)
@dataclass(frozen=True)
class PublicProbe:url:str;kind:str="http";timeout_seconds:int=30;deployment_identity_header:str|None=None
@dataclass(frozen=True)
class RunlessProofPlan:
    task_id:str;workstream:str;commands:tuple[tuple[str,...],...];artifacts:tuple[str,...];dependencies:tuple[str,...];probes:tuple[PublicProbe,...]=();timeout_seconds:int=900;live_ttl_seconds:int=900;freeze_token:str=""
    def validate(self):
        if not self.task_id or not self.workstream or not self.freeze_token:raise ValueError("RUNLESS_PLAN_REQUIRED_FIELDS")
        for c in self.commands:validate_command(c)
        if self.timeout_seconds<=0 or self.live_ttl_seconds<=0:raise ValueError("RUNLESS_PLAN_BAD_TIMEOUT")
def validate_command(command):
    cmd=tuple(command);text=" ".join(cmd)
    if BAD_SHELL.search(text):raise ValueError("RUNLESS_COMMAND_REJECTED")
    if len(cmd)>=3 and cmd[:3]==("python","-m","pytest"):return cmd
    if len(cmd)>=3 and cmd[:2]==("python","-m") and (cmd[2].startswith(APPROVED_MODULE_PREFIXES) or cmd[2]=="py_compile"):return cmd
    raise ValueError("RUNLESS_COMMAND_REJECTED")
def load_plan(task_id,root:Path):
    path=root/"devsystem"/"runless_proof_plans"/f"{task_id}.json"
    if not path.exists():raise FileNotFoundError("RUNLESS_PLAN_REQUIRED")
    r=json.loads(path.read_text());p=RunlessProofPlan(task_id=r["task_id"],workstream=r["workstream"],commands=tuple(tuple(x) for x in r.get("commands",[])),artifacts=tuple(r.get("artifacts",[])),dependencies=tuple(r.get("dependencies",[])),probes=tuple(PublicProbe(**x) for x in r.get("probes",[])),timeout_seconds=int(r.get("timeout_seconds",900)),live_ttl_seconds=int(r.get("live_ttl_seconds",900)),freeze_token=r["freeze_token"])
    if p.task_id!=task_id:raise ValueError("RUNLESS_PLAN_ID_MISMATCH")
    p.validate();return p
