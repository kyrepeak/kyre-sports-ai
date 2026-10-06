from __future__ import annotations
import json
from devsystem.runless_terminal_proof_receipt_v1 import validate_runless_receipt
class ReceiptStore:
    def __init__(self,backend,ref="runless-proof-receipts",base_path="devsystem/runless_proof_receipts"):self.backend,self.ref,self.base_path=backend,ref,base_path.rstrip("/")
    def put(self,receipt):
        validate_runless_receipt(receipt);pid=receipt["proof_id"];path=f"{self.base_path}/{pid}.json"
        if self.backend.exists(path,self.ref):raise ValueError("RUNLESS_RECEIPT_DUPLICATE_ID")
        self.backend.create_immutable(path,json.dumps(receipt,sort_keys=True,indent=2)+"\n",self.ref);return receipt["digest"]
    def get(self,proof_id):
        p=json.loads(self.backend.read(f"{self.base_path}/{proof_id}.json",self.ref));validate_runless_receipt(p);return p
    def reconstruct(self,proof_id):
        chain=[];seen=set();cur=self.get(proof_id)
        while cur:
            if cur["digest"] in seen:raise ValueError("RUNLESS_RECEIPT_LINEAGE_LOOP")
            seen.add(cur["digest"]);chain.append(cur);prior=cur.get("prior_proof_id");cur=self.get(prior) if prior else None
        return chain
