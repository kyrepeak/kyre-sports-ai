from __future__ import annotations
from devsystem.runless_terminal_proof_receipt_v1 import validate_runless_receipt
def publish_gate(client,head_sha,conclusion,receipt,gate_name="runless-final-gate"):
    if conclusion=="success":
        if not receipt:raise ValueError("RUNLESS_TERMINAL_RECEIPT_REQUIRED")
        validate_runless_receipt(receipt)
        if receipt["candidate_sha"]!=head_sha:raise ValueError("RUNLESS_GATE_SHA_MISMATCH")
    digest=receipt.get("digest") if receipt else None;return client.publish_check(head_sha,gate_name,conclusion,{"title":"Runless Proof Plane","summary":f"receipt={digest or 'pending'}"})
