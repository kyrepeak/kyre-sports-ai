import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

PROVE_URL = 'https://kyre-runless-proof.vercel.app/prove'


def build_payload():
    return {
        'task_id': 'universal-sports-source-finalization-v1-step7',
        'workstream': 'universal-sports-source-finalization-v1',
        'candidate_sha': '6e2d917d6603b0cb207ab35f9da72e20edc9fab7',
        'lease_id': 'SCOPE-LEASE-34BAA03E10769ACE383516A0',
        'authorization_id': 'universal-sports-source-finalization-v1-step7-final-authorization',
        'expected_main_sha': '67dad9d7711c39e2dd640d72ab7f5d28946d2d3e',
    }


def submit_proof(token, *, post=None):
    if not token:
        raise RuntimeError('RUNLESS_PROOF_AUTH_TOKEN_REQUIRED')
    if post is None:
        import httpx
        post = httpx.post
    response = post(
        PROVE_URL,
        headers={'Authorization': f'Bearer {token}'},
        json=build_payload(),
        timeout=240,
    )
    try:
        body = response.json()
    except Exception:
        body = {'detail': 'NON_JSON_RESPONSE'}
    return {'status_code': int(response.status_code), 'body': body}


app = FastAPI(title='Step 7 Runless Proof Transport', version='1')


@app.post('/step7-final-proof-transport')
def step7_final_proof_transport():
    try:
        result = submit_proof(os.environ.get('RUNLESS_PROOF_AUTH_TOKEN', ''))
    except RuntimeError:
        return JSONResponse(
            status_code=503,
            content={'status_code': 503, 'body': {'detail': 'TRANSPORT_CONFIGURATION_MISSING'}},
        )
    status_code = result['status_code']
    if status_code < 100 or status_code > 599:
        status_code = 502
    return JSONResponse(status_code=status_code, content=result)
