from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx


class TransportError(RuntimeError):
    pass


def project_transport_state(native_state: str) -> str:
    mapping = {
        "IDENTIFY": "REQUESTED",
        "2A_LOCK": "QUEUED",
        "FINGERPRINT": "QUEUED",
        "REUSE_OR_PROVE": "RUNNING",
        "PUBLIC_CHECK_IF_REQUIRED": "RUNNING",
        "RECEIPT": "RUNNING",
        "RUNLESS_FINAL_GATE": "RUNNING",
        "MERGE_AUTHORIZED": "SUCCEEDED",
        "MERGED": "SUCCEEDED",
        "POST_MERGE_VERIFY": "SUCCEEDED",
        "FREEZE": "SUCCEEDED",
        "READ_BACK": "SUCCEEDED",
        "GREEN_FROZEN": "SUCCEEDED",
        "FAILED": "FAILED",
    }
    try:
        return mapping[native_state]
    except KeyError as exc:
        raise TransportError(f"RUNLESS_TRANSPORT_UNKNOWN_STATE:{native_state}") from exc


def normalize_transport_response(payload: dict[str, Any]) -> dict[str, Any]:
    proof_id = payload.get("proof_id")
    native_state = payload.get("state") or payload.get("status")
    candidate_sha = payload.get("candidate_sha")
    if not isinstance(proof_id, str) or not isinstance(native_state, str):
        raise TransportError("RUNLESS_TRANSPORT_RESPONSE_IDENTITY_REQUIRED")
    return {
        "proof_id": proof_id,
        "candidate_sha": candidate_sha,
        "state": native_state,
        "transport_state": project_transport_state(native_state),
        "fencing_generation": payload.get("fencing_generation", 0),
        "receipt_digest": payload.get("receipt_digest"),
        "gate_check_run_id": payload.get("gate_check_run_id"),
        "execution_identity": payload.get("execution_identity") or proof_id,
    }


def _safe_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except Exception:
        return "RUNLESS_TRANSPORT_HTTP_ERROR"
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str) and detail:
        token = detail.strip().split()[0][:160]
        if token.startswith("RUNLESS_"):
            return token
    return "RUNLESS_TRANSPORT_HTTP_ERROR"


class TransportClient:
    def __init__(self, *, base_url: str, bearer_token: str, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.timeout_seconds = timeout_seconds
        self._client = httpx.Client(timeout=timeout_seconds)

    def _request(self, method: str, path: str, *, json_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self._client.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self.bearer_token}"},
                json=json_payload,
            )
        except httpx.HTTPError as exc:
            raise TransportError(f"RUNLESS_TRANSPORT_HTTP_UNAVAILABLE:{type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise TransportError(f"RUNLESS_TRANSPORT_HTTP_{response.status_code}:{_safe_detail(response)}")
        try:
            payload = response.json()
        except Exception as exc:
            raise TransportError("RUNLESS_TRANSPORT_BAD_JSON") from exc
        if not isinstance(payload, dict):
            raise TransportError("RUNLESS_TRANSPORT_BAD_JSON")
        return payload

    def request_proof(self, payload: dict[str, Any]) -> dict[str, Any]:
        return normalize_transport_response(self._request("POST", "/prove", json_payload=payload))

    def get_status(self, proof_id: str) -> dict[str, Any]:
        return normalize_transport_response(self._request("GET", f"/status/{proof_id}"))

    def get_receipt(self, proof_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/receipts/{proof_id}")
        if payload.get("proof_id") != proof_id:
            raise TransportError("RUNLESS_TRANSPORT_RECEIPT_IDENTITY_MISMATCH")
        return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="runless-transport")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prove", "status", "receipt"):
        p = sub.add_parser(name)
        p.add_argument("--base-url", required=True)
        if name == "prove":
            p.add_argument("--task-id", required=True)
            p.add_argument("--workstream", required=True)
            p.add_argument("--candidate-sha", required=True)
            p.add_argument("--lease-id", required=True)
            p.add_argument("--authorization-id", required=True)
            p.add_argument("--expected-main-sha")
        else:
            p.add_argument("--proof-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get("RUNLESS_PROOF_AUTH_TOKEN")
    if not token:
        print(json.dumps({"error": "RUNLESS_TRANSPORT_AUTH_TOKEN_REQUIRED"}, sort_keys=True), file=sys.stderr)
        return 2
    try:
        client = TransportClient(base_url=args.base_url, bearer_token=token)
        if args.command == "prove":
            payload = {
                "task_id": args.task_id,
                "workstream": args.workstream,
                "candidate_sha": args.candidate_sha,
                "lease_id": args.lease_id,
                "authorization_id": args.authorization_id,
            }
            if args.expected_main_sha:
                payload["expected_main_sha"] = args.expected_main_sha
            result = client.request_proof(payload)
        elif args.command == "status":
            result = client.get_status(args.proof_id)
        else:
            result = client.get_receipt(args.proof_id)
        print(json.dumps(result, sort_keys=True))
        return 0
    except TransportError as exc:
        print(json.dumps({"error": str(exc)[:240]}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
