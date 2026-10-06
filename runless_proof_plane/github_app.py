from __future__ import annotations
import hashlib,hmac,time
from dataclasses import dataclass,field
import httpx,jwt
from .config import Settings
@dataclass
class GithubAppAuth:
    settings:Settings; client:httpx.Client|None=None; _cached_token:str|None=None; _cached_until:float=0.0; _seen_nonces:dict[str,float]=field(default_factory=dict)
    def _app_jwt(self):
        now=int(time.time()); return jwt.encode({"iat":now-30,"exp":now+540,"iss":self.settings.github_app_id},self.settings.github_app_private_key,algorithm="RS256")
    def installation_token(self):
        now=time.time()
        if self._cached_token and now<self._cached_until-60:return self._cached_token
        if not self.settings.github_app_installation_id:raise RuntimeError("RUNLESS_INSTALLATION_ID_REQUIRED")
        c=self.client or httpx.Client(timeout=15); u=f"https://api.github.com/app/installations/{self.settings.github_app_installation_id}/access_tokens"; r=c.post(u,headers={"Authorization":f"Bearer {self._app_jwt()}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}); r.raise_for_status(); p=r.json(); token=p.get("token")
        if not token or not p.get("expires_at"):raise RuntimeError("RUNLESS_BAD_INSTALLATION_TOKEN_RESPONSE")
        self._cached_token=token; self._cached_until=now+2700; return token
    def verify_webhook_signature(self,body:bytes,signature:str,nonce:str|None=None,now:float|None=None):
        secret=self.settings.github_webhook_secret
        if not secret:raise RuntimeError("RUNLESS_WEBHOOK_SECRET_REQUIRED")
        expected="sha256="+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,signature or ""):raise ValueError("RUNLESS_WEBHOOK_SIGNATURE_INVALID")
        if nonce:
            ts=time.time() if now is None else now; self._seen_nonces={k:v for k,v in self._seen_nonces.items() if ts-v<600}
            if nonce in self._seen_nonces:raise ValueError("RUNLESS_WEBHOOK_REPLAY")
            self._seen_nonces[nonce]=ts
