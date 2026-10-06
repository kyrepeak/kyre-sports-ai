from __future__ import annotations
import os
from dataclasses import dataclass
@dataclass(frozen=True)
class Settings:
    repository:str="kyrepeak/kyre-sports-ai"; receipt_ref:str="runless-proof-receipts"; receipt_path:str="devsystem/runless_proof_receipts"; gate_name:str="runless-final-gate"; proof_timeout_seconds:int=900; production_proof_ttl_seconds:int=900; bootstrap:bool=True; github_app_id:str|None=None; github_app_installation_id:str|None=None; github_app_private_key:str|None=None; github_webhook_secret:str|None=None; dry_run_on_start:bool=False; dry_run_candidate:str|None=None; source_branch:str="runless-proof-plane-v1"; deployment_identity:str|None=None
    @classmethod
    def from_env(cls,env:dict[str,str]|None=None):
        e=os.environ if env is None else env; full=e.get("RPP_FULL_APP_ENABLED","").strip()=="1"
        s=cls(repository=e.get("GITHUB_REPOSITORY","kyrepeak/kyre-sports-ai"),receipt_ref=e.get("RPP_RECEIPT_REF","runless-proof-receipts"),receipt_path=e.get("RPP_RECEIPT_PATH","devsystem/runless_proof_receipts"),gate_name=e.get("RPP_GATE_NAME","runless-final-gate"),proof_timeout_seconds=int(e.get("RPP_PROOF_TIMEOUT_SECONDS","900")),production_proof_ttl_seconds=int(e.get("RPP_PRODUCTION_PROOF_TTL_SECONDS","900")),bootstrap=not full,github_app_id=e.get("GITHUB_APP_ID"),github_app_installation_id=e.get("GITHUB_APP_INSTALLATION_ID"),github_app_private_key=e.get("GITHUB_APP_PRIVATE_KEY"),github_webhook_secret=e.get("GITHUB_WEBHOOK_SECRET"),dry_run_on_start=e.get("RPP_DRY_RUN_ON_START","").strip()=="1",dry_run_candidate=e.get("RPP_DRY_RUN_CANDIDATE"),source_branch=e.get("RPP_SOURCE_BRANCH","runless-proof-plane-v1"),deployment_identity=e.get("RENDER_GIT_COMMIT") or e.get("RENDER_SERVICE_ID"))
        if not s.bootstrap:
            missing=[k for k,v in {"GITHUB_APP_ID":s.github_app_id,"GITHUB_APP_INSTALLATION_ID":s.github_app_installation_id,"GITHUB_APP_PRIVATE_KEY":s.github_app_private_key}.items() if not v]
            if missing: raise RuntimeError("RUNLESS_SECRETS_REQUIRED:"+",".join(missing))
        return s
