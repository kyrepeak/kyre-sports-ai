from __future__ import annotations
import re,httpx
from .github_app import GithubAppAuth
_FORBIDDEN=(re.compile(r"/actions/workflows/.+/dispatches(?:$|\?)"),re.compile(r"/actions/runs/.+/(?:rerun|rerun-failed-jobs)(?:$|\?)"))
class GithubClient:
    def __init__(self,auth:GithubAppAuth,repository:str,client:httpx.Client|None=None):self.auth,self.repository=auth,repository;self.client=client or httpx.Client(timeout=20);self.base=f"https://api.github.com/repos/{repository}"
    @staticmethod
    def validate_path(path:str):
        if any(p.search(path) for p in _FORBIDDEN):raise ValueError("RUNLESS_ACTIONS_API_FORBIDDEN")
    def request(self,method,path,**kwargs):
        self.validate_path(path);t=self.auth.installation_token();r=self.client.request(method,self.base+path,headers={"Authorization":f"Bearer {t}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},**kwargs);r.raise_for_status();return None if r.status_code==204 else r.json()
    def branch_sha(self,branch):return self.request("GET",f"/git/ref/heads/{branch}")["object"]["sha"]
    def content(self,path,ref=None):return self.request("GET",f"/contents/{path}"+(f"?ref={ref}" if ref else ""))
    def publish_check(self,sha,name,conclusion,output):
        p={"name":name,"head_sha":sha,"status":"completed" if conclusion else "in_progress","output":output}
        if conclusion:p["conclusion"]=conclusion
        return self.request("POST","/check-runs",json=p)
    def create_commit_status(self,sha,state,context,description):return self.request("POST",f"/statuses/{sha}",json={"state":state,"context":context,"description":description[:140]})
