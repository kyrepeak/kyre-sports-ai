from __future__ import annotations
import base64,json
from devsystem.runless_terminal_proof_receipt_v1 import validate_runless_receipt
class GithubReceiptBackend:
    def __init__(self,client,base_sha,ref="runless-proof-receipts",base_path="devsystem/runless_proof_receipts"):
        self.client,self.base_sha,self.ref,self.base_path=client,base_sha,ref.replace('refs/heads/',''),base_path.rstrip('/')
    def _assert(self,path,ref):
        if ref.replace('refs/heads/','')!=self.ref or not path.startswith(self.base_path+'/'):raise RuntimeError("RUNLESS_RECEIPT_SCOPE_VIOLATION")
    def ensure_ref(self):
        if self.client.get_ref(self.ref) is None:self.client.create_ref(self.ref,self.base_sha)
    def exists(self,path,ref):
        self._assert(path,ref);self.ensure_ref();return self.client.content(path,self.ref,allow_404=True) is not None
    def read(self,path,ref):
        self._assert(path,ref);self.ensure_ref();p=self.client.content(path,self.ref)
        return base64.b64decode(p['content']).decode()
    def create_immutable(self,path,content,ref):
        self._assert(path,ref);self.ensure_ref()
        if self.client.content(path,self.ref,allow_404=True) is not None:raise ValueError("RUNLESS_RECEIPT_DUPLICATE_ID")
        self.client.put_content(path,content,self.ref,f"runless receipt: {path.rsplit('/',1)[-1]}")
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
