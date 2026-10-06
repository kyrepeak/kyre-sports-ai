from __future__ import annotations
from fastapi import FastAPI,HTTPException,Request
from . import VERSION
from .config import Settings
from .models import ProofRequest
from .orchestrator import ProofOrchestrator
def create_app(settings=None):
    settings=settings or Settings.from_env();app=FastAPI(title="Runless Proof Plane",version="1");app.state.settings=settings;app.state.orchestrator=ProofOrchestrator();app.state.receipts={}
    @app.get("/health")
    def health():return {"status":"healthy","service":"runless-proof-plane","version":VERSION,"mode":"bootstrap" if settings.bootstrap else "full","github_actions_enabled":False,"proof_authority":"disabled" if settings.bootstrap else "enabled","repository":settings.repository}
    @app.post("/prove")
    def prove(req:ProofRequest):
        if settings.bootstrap:raise HTTPException(503,"RUNLESS_PROOF_AUTHORITY_DISABLED")
        raise HTTPException(409,"RUNLESS_PLAN_REQUIRED")
    @app.get("/status/{proof_id}")
    def status(proof_id):
        try:return app.state.orchestrator.status(proof_id)
        except KeyError:raise HTTPException(404,"RUNLESS_PROOF_NOT_FOUND")
    @app.get("/receipts/{proof_id}")
    def receipt(proof_id):
        if proof_id not in app.state.receipts:raise HTTPException(404,"RUNLESS_RECEIPT_NOT_FOUND")
        return app.state.receipts[proof_id]
    @app.post("/github/webhook")
    async def webhook(request:Request):
        if settings.bootstrap:raise HTTPException(503,"RUNLESS_PROOF_AUTHORITY_DISABLED")
        return {"accepted":True}
    return app
app=create_app()
