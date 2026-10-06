from __future__ import annotations
import base64,re,httpx
from urllib.parse import quote
from .github_app import GithubAppAuth
_FORBIDDEN=(re.compile(r"/actions/workflows/.+/dispatches(?:$|\?)"),re.compile(r"/actions/runs/.+/(?:rerun|rerun-failed-jobs)(?:$|\?)"))
class GithubClient:
    def __init__(self,auth:GithubAppAuth,repository:str,client:httpx.Client|None=None):
        self.auth,self.repository=auth,repository;self.client=client or httpx.Client(timeout=20);self.base=f"https://api.github.com/repos/{repository}"
    @staticmethod
    def validate_path(path:str):
        if any(p.search(path) for p in _FORBIDDEN):raise ValueError("RUNLESS_ACTIONS_API_FORBIDDEN")
    def request(self,method,path,*,allow_404=False,**kwargs):
        self.validate_path(path);t=self.auth.installation_token();r=self.client.request(method,self.base+path,headers={"Authorization":f"Bearer {t}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},**kwargs)
        if allow_404 and r.status_code==404:return None
        r.raise_for_status();return None if r.status_code==204 else r.json()
    def repository_info(self):return self.request("GET","")
    def commit(self,sha):return self.request("GET",f"/commits/{sha}")
    def branch_sha(self,branch):return self.request("GET",f"/git/ref/heads/{quote(branch,safe='/')}")["object"]["sha"]
    def get_ref(self,branch):return self.request("GET",f"/git/ref/heads/{quote(branch,safe='/')}",allow_404=True)
    def create_ref(self,branch,sha):return self.request("POST","/git/refs",json={"ref":f"refs/heads/{branch}","sha":sha})
    def content(self,path,ref=None,allow_404=False):return self.request("GET",f"/contents/{quote(path,safe='/')}"+(f"?ref={quote(ref,safe='/')}" if ref else ""),allow_404=allow_404)
    def put_content(self,path,text,branch,message):
        payload={"message":message,"content":base64.b64encode(text.encode()).decode(),"branch":branch}
        return self.request("PUT",f"/contents/{quote(path,safe='/')}",json=payload)
    def update_content(self,path,text,branch,message,sha):
        payload={"message":message,"content":base64.b64encode(text.encode()).decode(),"branch":branch,"sha":sha}
        return self.request("PUT",f"/contents/{quote(path,safe='/')}",json=payload)
    def tree_blobs(self,sha):
        commit=self.commit(sha);tree_sha=commit["commit"]["tree"]["sha"];tree=self.request("GET",f"/git/trees/{tree_sha}?recursive=1")
        return {item["path"]:item["sha"] for item in tree.get("tree",[]) if item.get("type")=="blob"}
    def publish_check(self,sha,name,conclusion,output):
        p={"name":name,"head_sha":sha,"status":"completed" if conclusion else "in_progress","output":output}
        if conclusion:p["conclusion"]=conclusion
        return self.request("POST","/check-runs",json=p)
    def create_commit_status(self,sha,state,context,description):return self.request("POST",f"/statuses/{sha}",json={"state":state,"context":context,"description":description[:140]})
