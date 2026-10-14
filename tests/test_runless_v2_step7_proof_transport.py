import importlib.util
import os
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).parents[1] / 'runless_v2' / 'api' / 'index.py'
SPEC = importlib.util.spec_from_file_location('step7_proof_transport', MODULE_PATH)
transport = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(transport)

EXPECTED = {
    'task_id': 'universal-sports-source-finalization-v1-step7',
    'workstream': 'universal-sports-source-finalization-v1',
    'candidate_sha': '6e2d917d6603b0cb207ab35f9da72e20edc9fab7',
    'lease_id': 'SCOPE-LEASE-A70614DFEA642E4A5501A845',
    'authorization_id': 'universal-sports-source-finalization-v1-step7-final-authorization',
    'expected_main_sha': '67dad9d7711c39e2dd640d72ab7f5d28946d2d3e',
}


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            'proof_id': 'proof-1',
            'status': 'MERGE_AUTHORIZED',
            'candidate_sha': EXPECTED['candidate_sha'],
        }


class TransportTests(unittest.TestCase):
    def test_exact_identity_and_secret_preserving_submission(self):
        self.assertEqual(transport.build_payload(), EXPECTED)
        calls = []

        def fake_post(url, *, headers, json, timeout):
            calls.append((url, headers, json, timeout))
            return FakeResponse()

        result = transport.submit_proof('top-secret', post=fake_post)
        self.assertEqual(len(calls), 1)
        url, headers, body, timeout = calls[0]
        self.assertEqual(url, 'https://kyre-runless-proof.vercel.app/prove')
        self.assertEqual(headers, {'Authorization': 'Bearer top-secret'})
        self.assertEqual(body, EXPECTED)
        self.assertGreaterEqual(timeout, 120)
        self.assertEqual(result['status_code'], 200)
        self.assertEqual(result['body']['status'], 'MERGE_AUTHORIZED')
        self.assertNotIn('top-secret', repr(result))

    def test_missing_token_fails_before_network(self):
        calls = []
        with self.assertRaises(RuntimeError):
            transport.submit_proof('', post=lambda *a, **k: calls.append((a, k)))
        self.assertEqual(calls, [])

    def test_preview_endpoint_calls_submit_once_and_returns_sanitized_result(self):
        from fastapi.testclient import TestClient

        original = transport.submit_proof
        calls = []

        def fake_submit(token, **kwargs):
            calls.append(token)
            return {'status_code': 200, 'body': {'status': 'MERGE_AUTHORIZED'}}

        transport.submit_proof = fake_submit
        old = os.environ.get('RUNLESS_PROOF_AUTH_TOKEN')
        os.environ['RUNLESS_PROOF_AUTH_TOKEN'] = 'endpoint-secret'
        try:
            response = TestClient(transport.app).post('/step7-final-proof-transport')
        finally:
            transport.submit_proof = original
            if old is None:
                os.environ.pop('RUNLESS_PROOF_AUTH_TOKEN', None)
            else:
                os.environ['RUNLESS_PROOF_AUTH_TOKEN'] = old
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ['endpoint-secret'])
        self.assertEqual(response.json()['body']['status'], 'MERGE_AUTHORIZED')
        self.assertNotIn('endpoint-secret', response.text)


if __name__ == '__main__':
    unittest.main()
