from __future__ import annotations
import os,time
from fastapi import FastAPI,HTTPException,Request
from . import VERSION
from .config import Settings
from .dry_run import certify_dry_run
from .github_app import GithubAppAuth
from .github_client import GithubClient
from .models import ProofRequest
from .orchestrator import ProofOrchestrator
from .registry import freeze_task13
from .step6_registry import freeze_step6
from .step7_control import apply_step7_app_patch
from .step7_registry import freeze_step7
from .step8_registry import freeze_step8

def create_app(settings=None):
    settings=settings or Settings.from_env();app=FastAPI(title="Runless Proof Plane",version="1");app.state.settings=settings;app.state.orchestrator=ProofOrchestrator();app.state.receipts={};app.state.dry_run={'status':'NOT_RUN'};app.state.freeze={'status':'NOT_RUN'};app.state.registry={'status':'NOT_RUN'};app.state.app_patch={'status':'NOT_RUN'};app.state.github_auth=GithubAppAuth(settings);app.state.github_client=GithubClient(app.state.github_auth,settings.repository);app.state.github_diag_cache=None
    @app.on_event('startup')
    def startup_dry_run():
        if not settings.bootstrap and settings.dry_run_on_start:
            try:
                app.state.dry_run=certify_dry_run(settings)
                if settings.final_freeze_on_start:
                    if app.state.dry_run.get('status')!='GREEN':raise RuntimeError('RUNLESS_FINAL_FREEZE_REQUIRES_GREEN_PROOF')
                    app.state.freeze=freeze_task13(app.state.github_client,settings.dry_run_candidate,settings.freeze_token)
            except Exception as exc:
                if app.state.dry_run.get('status')!='GREEN':app.state.dry_run={'status':'FAIL','error':type(exc).__name__,'detail':str(exc)[:240]}
                else:app.state.freeze={'status':'FAIL','error':type(exc).__name__,'detail':str(exc)[:240]}
        if not settings.bootstrap and os.environ.get('RPP_STEP6_FREEZE_ON_START','0')=='1':
            try:
                app.state.registry=freeze_step6(
                    app.state.github_client,
                    os.environ['RPP_STEP6_FREEZE_MERGED_SHA'],
                    os.environ.get('RPP_STEP6_FREEZE_TOKEN','WNBA_PRA_REPAIR_V1_STEP6_FROZEN'),
                )
            except Exception as exc:
                app.state.registry={'status':'FAIL','error':type(exc).__name__,'detail':str(exc)[:240]}
        if not settings.bootstrap and os.environ.get('RPP_STEP7_APP_PATCH_ON_START','0')=='1':
            try:
                app.state.app_patch=apply_step7_app_patch(app.state.github_client)
            except Exception as exc:
                app.state.app_patch={'status':'FAIL','error':type(exc).__name__,'detail':str(exc)[:240]}
        if not settings.bootstrap and os.environ.get('RPP_STEP7_FREEZE_ON_START','0')=='1':
            try:
                app.state.registry=freeze_step7(
                    app.state.github_client,
                    os.environ['RPP_STEP7_FREEZE_MERGED_SHA'],
                    os.environ.get('RPP_STEP7_FREEZE_TOKEN','WNBA_PRA_REPAIR_V1_STEP7_FROZEN'),
                )
            except Exception as exc:
                app.state.registry={'status':'FAIL','error':type(exc).__name__,'detail':str(exc)[:240]}
        if not settings.bootstrap and os.environ.get('RPP_STEP8_FREEZE_ON_START','0')=='1':
            try:
                app.state.registry=freeze_step8(
                    app.state.github_client,
                    os.environ['RPP_STEP8_FREEZE_MERGED_SHA'],
                    os.environ.get('RPP_STEP8_FREEZE_TOKEN','WNBA_PRA_REPAIR_V1_STEP8_FROZEN'),
                )
            except Exception as exc:
                app.state.registry={'status':'FAIL','error':type(exc).__name__,'detail':str(exc)[:240]}
    @app.get("/health")
    def health():return {"status":"healthy","service":"runless-proof-plane","version":VERSION,"mode":"bootstrap" if settings.bootstrap else "full","github_actions_enabled":False,"proof_authority":"disabled" if settings.bootstrap else "enabled","repository":settings.repository,"github_app_configured":bool(settings.github_app_id and settings.github_app_installation_id and settings.github_app_private_key),"dry_run":app.state.dry_run.get('status'),"freeze":app.state.freeze.get('status'),"registry":app.state.registry.get('status'),"app_patch":app.state.app_patch.get('status')}
    @app.get('/diagnostics/github')
    def github_diag():
        if settings.bootstrap:raise HTTPException(503,'RUNLESS_PROOF_AUTHORITY_DISABLED')
        try:
            now=time.monotonic();cached=app.state.github_diag_cache
            if cached and now<cached['expires_at']:return cached['value']
            repo=app.state.github_client.repository_info();value={'status':'GREEN','repository':repo.get('full_name'),'installation_auth':True};app.state.github_diag_cache={'expires_at':now+30,'value':value};return value
        except Exception as exc:raise HTTPException(503,f'RUNLESS_GITHUB_AUTH_FAILED:{type(exc).__name__}')
    @app.get('/dry-run/status')
    def dry_status():return app.state.dry_run
    @app.get('/freeze/status')
    def freeze_status():return app.state.freeze
    @app.get('/registry/status')
    def registry_status():return app.state.registry
    @app.get('/app-patch/status')
    def app_patch_status():return app.state.app_patch
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
        try:app.state.github_auth.verify_webhook_signature(body,sig,nonce=nonce)
        except Exception:raise HTTPException(401,"RUNLESS_WEBHOOK_SIGNATURE_INVALID")
        return {"accepted":True}
    return app
app=create_app()
