from __future__ import annotations
from fastapi import FastAPI,HTTPException,Request
from . import VERSION
from .config import Settings
from .dry_run import certify_dry_run
from .github_app import GithubAppAuth
from .github_client import GithubClient
from .models import ProofRequest
from .orchestrator import ProofOrchestrator
def create_app(settings=None):
    settings=settings or Settings.from_env();app=FastAPI(title="Runless Proof Plane",version="1");app.state.settings=settings;app.state.orchestrator=ProofOrchestrator();app.state.receipts={};app.state.dry_run={'status':'NOT_RUN'}
    @app.on_event('startup')
    def startup_dry_run():
        if not settings.bootstrap and settings.dry_run_on_start:
            try:app.state.dry_run=certify_dry_run(settings)
            except Exception as exc:app.state.dry_run={'status':'FAIL','error':type(exc).__name__,'detail':str(exc)[:240]}
    @app.get("/health")
    def health():return {"status":"healthy","service":"runless-proof-plane","version":VERSION,"mode":"bootstrap" if settings.bootstrap else "full","github_actions_enabled":False,"proof_authority":"disabled" if settings.bootstrap else "enabled","repository":settings.repository,"github_app_configured":bool(settings.github_app_id and settings.github_app_installation_id and settings.github_app_private_key),"dry_run":app.state.dry_run.get('status')}
    @app.get('/diagnostics/github')
    def github_diag():
        if settings.bootstrap:raise HTTPException(503,'RUNLESS_PROOF_AUTHORITY_DISABLED')
        try:
            client=GithubClient(GithubAppAuth(settings),settings.repository);repo=client.repository_info();return {'status':'GREEN','repository':repo.get('full_name'),'installation_auth':True}
        except Exception as exc:raise HTTPException(503,f'RUNLESS_GITHUB_AUTH_FAILED:{type(exc).__name__}')
    @app.get('/dry-run/status')
    def dry_status():return app.state.dry_run
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
        if not settings.github_webhook_secret:raise HTTPException(503,"RUNLESS_WEBHOOK_SECRET_REQUIRED")
        body=await request.body();sig=request.headers.get('x-hub-signature-256','');nonce=request.headers.get('x-github-delivery')
        try:GithubAppAuth(settings).verify_webhook_signature(body,sig,nonce=nonce)
        except Exception:raise HTTPException(401,"RUNLESS_WEBHOOK_SIGNATURE_INVALID")
        return {"accepted":True}
    return app
app=create_app()
