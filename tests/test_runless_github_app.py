import hashlib,hmac,pytest
from runless_proof_plane.config import Settings
from runless_proof_plane.github_app import GithubAppAuth
def test_webhook_valid_invalid_and_replay():
 s=Settings(github_webhook_secret='s');a=GithubAppAuth(s);b=b'{}';sig='sha256='+hmac.new(b's',b,hashlib.sha256).hexdigest();a.verify_webhook_signature(b,sig,nonce='n',now=1)
 with pytest.raises(ValueError):a.verify_webhook_signature(b,'sha256=bad')
 with pytest.raises(ValueError,match='REPLAY'):a.verify_webhook_signature(b,sig,nonce='n',now=2)
