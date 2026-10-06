from __future__ import annotations
import os
from fastapi import FastAPI
SERVICE_NAME="runless-proof-plane"
def create_bootstrap_app():
    if os.getenv("RPP_FULL_APP_ENABLED","").strip()=="1":
        from .api import app as full_app
        return full_app
    app=FastAPI(title="Runless Proof Plane Bootstrap",version="1")
    @app.get("/health")
    async def health():return {"status":"healthy","service":SERVICE_NAME,"proof_authority":"disabled","mode":"bootstrap","github_actions_enabled":False}
    return app
app=create_bootstrap_app()
