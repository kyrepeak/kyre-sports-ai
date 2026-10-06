from __future__ import annotations
import hashlib,time,httpx
from .models import FailureClass,SliceEvidence
def run_public_probe(probe,deployment_identity=None,client=None):
    c=client or httpx.Client(timeout=probe.timeout_seconds,follow_redirects=True);start=time.monotonic()
    try:
        r=c.get(probe.url);text=r.text;ok=200<=r.status_code<400;observed=r.headers.get(probe.deployment_identity_header) if probe.deployment_identity_header else deployment_identity
        if deployment_identity and observed and observed!=deployment_identity:ok=False
        return SliceEvidence(name=f"public:{probe.url}",ok=ok,stdout_digest=hashlib.sha256(text.encode()).hexdigest(),duration_seconds=time.monotonic()-start,failure_class=FailureClass.NONE if ok else FailureClass.PUBLIC_PROOF,deployment_identity=observed)
    except Exception:return SliceEvidence(name=f"public:{probe.url}",ok=False,duration_seconds=time.monotonic()-start,failure_class=FailureClass.INFRA,deployment_identity=deployment_identity)
