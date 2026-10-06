from types import SimpleNamespace
from runless_proof_plane.public_probe import run_public_probe
class Resp:status_code=200;text='ok';headers={'X-Deploy':'d'}
class C:
 def get(self,u):return Resp()
def test_public_identity():
 p=SimpleNamespace(url='https://x',timeout_seconds=1,deployment_identity_header='X-Deploy');assert run_public_probe(p,'d',C()).ok
 assert not run_public_probe(p,'other',C()).ok
