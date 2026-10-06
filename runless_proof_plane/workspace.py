from __future__ import annotations
import os,shutil,subprocess,tempfile
from pathlib import Path
class CandidateWorkspace:
    def __init__(self,repository_url,candidate_sha,token=None):self.repository_url,self.candidate_sha,self.token=repository_url,candidate_sha,token;self.path=None;self._askpass=None
    def __enter__(self):
        self.path=Path(tempfile.mkdtemp(prefix="runless-"));env=os.environ.copy();env["GIT_TERMINAL_PROMPT"]="0"
        if self.token:
            self._askpass=self.path/".askpass.sh";self._askpass.write_text('#!/bin/sh\necho "$RUNLESS_GIT_TOKEN"\n');self._askpass.chmod(0o700);env["GIT_ASKPASS"]=str(self._askpass);env["RUNLESS_GIT_TOKEN"]=self.token
        subprocess.run(["git","init","-q",str(self.path)],check=True,env=env,capture_output=True,text=True);subprocess.run(["git","-C",str(self.path),"remote","add","origin",self.repository_url],check=True,env=env,capture_output=True,text=True);subprocess.run(["git","-C",str(self.path),"fetch","-q","--depth=1","origin",self.candidate_sha],check=True,env=env,capture_output=True,text=True);subprocess.run(["git","-C",str(self.path),"checkout","-q","--detach","FETCH_HEAD"],check=True,env=env,capture_output=True,text=True)
        actual=subprocess.check_output(["git","-C",str(self.path),"rev-parse","HEAD"],text=True).strip()
        if actual!=self.candidate_sha:raise RuntimeError("RUNLESS_STALE_WORKSPACE")
        if self._askpass and self._askpass.exists():self._askpass.unlink()
        return self
    def cleanup(self):
        if self.path and self.path.exists():shutil.rmtree(self.path,ignore_errors=True)
    def __exit__(self,*_):self.cleanup()
