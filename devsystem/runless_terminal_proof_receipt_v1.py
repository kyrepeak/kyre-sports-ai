from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
def canonical(payload):return json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()
def digest_payload(payload):return hashlib.sha256(canonical({k:v for k,v in payload.items() if k!="digest"})).hexdigest()
def build_runless_receipt(**kwargs):
    required=("proof_id","task_id","project","workstream","step","candidate_sha","artifact_map","dependency_map","registry_before","registry_after","evidence_digests","failure_class");missing=[k for k in required if k not in kwargs]
    if missing:raise ValueError("RUNLESS_RECEIPT_MISSING:"+",".join(missing))
    p=dict(kwargs);p.setdefault("created_at",datetime.now(timezone.utc).isoformat());p.setdefault("prior_digest",None);p["digest"]=digest_payload(p);return p
def validate_runless_receipt(payload):
    if payload.get("digest")!=digest_payload(payload):raise ValueError("RUNLESS_RECEIPT_TAMPERED")
    if len(payload.get("candidate_sha",""))!=40:raise ValueError("RUNLESS_RECEIPT_BAD_SHA")
    return True
