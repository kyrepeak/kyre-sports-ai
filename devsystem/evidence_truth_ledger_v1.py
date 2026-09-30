"""MONSTER V3 Step 3 — Evidence Graph / Truth Ledger V1.

Dependency-light control-plane evidence identity. The ledger preserves historical
proof while deciding whether that proof still certifies the exact PR head,
merged main, or deployed commit. It performs no network calls and cannot mutate
product/runtime behavior.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_EVIDENCE_TRUTH_LEDGER_V1"
NETWORK_CALLS = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_SCOPES = {"PR_HEAD", "MERGED_MAIN", "DEPLOYMENT"}
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")


class EvidenceTruthFailure(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(payload: Mapping[str, Any]) -> str:
    return "TRUTH-" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:24].upper()


def _full_sha(value: Any, *, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA_RE.match(text):
        raise EvidenceTruthFailure(f"{field} must be a full 40-character SHA")
    return text


def _positive_int(value: Any, *, field: str, required: bool = True) -> int | None:
    if value is None:
        if required:
            raise EvidenceTruthFailure(f"{field} is required")
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceTruthFailure(f"{field} must be an integer") from exc
    if parsed <= 0:
        raise EvidenceTruthFailure(f"{field} must be positive")
    return parsed


def build_evidence_record(
    *,
    evidence_id: str,
    checkpoint_id: str,
    contract_id: str,
    scope: str,
    repository: str,
    commit_sha: str,
    workflow_run_id: int | None,
    job_id: int | None,
    proof_id: str,
    conclusion: str,
    frozen: bool,
    deployment_id: str | None = None,
    deployment_sha: str | None = None,
) -> dict[str, Any]:
    evidence_id = str(evidence_id or "").strip()
    checkpoint_id = str(checkpoint_id or "").strip()
    contract_id = str(contract_id or "").strip()
    proof_id = str(proof_id or "").strip()
    repo = str(repository or "").strip()
    scope_value = str(scope or "").strip().upper()

    if not evidence_id:
        raise EvidenceTruthFailure("evidence_id is required")
    if not checkpoint_id:
        raise EvidenceTruthFailure("checkpoint_id is required")
    if not contract_id:
        raise EvidenceTruthFailure("contract_id is required")
    if scope_value not in _SCOPES:
        raise EvidenceTruthFailure("scope is invalid")
    if not _REPO_RE.match(repo):
        raise EvidenceTruthFailure("repository must be owner/name")
    if not proof_id:
        raise EvidenceTruthFailure("proof_id is required")

    commit = _full_sha(commit_sha, field="commit_sha")
    run_id = _positive_int(workflow_run_id, field="workflow_run_id", required=True)
    parsed_job_id = _positive_int(job_id, field="job_id", required=False)

    deploy_id = str(deployment_id).strip() if deployment_id is not None else None
    deploy_sha: str | None = None
    if deployment_sha is not None:
        deploy_sha = _full_sha(deployment_sha, field="deployment_sha")
    if scope_value == "DEPLOYMENT":
        if not deploy_id:
            raise EvidenceTruthFailure("DEPLOYMENT scope requires deployment_id")
        if deploy_sha is None:
            raise EvidenceTruthFailure("DEPLOYMENT scope requires deployment_sha")

    return {
        "evidence_id": evidence_id,
        "checkpoint_id": checkpoint_id,
        "contract_id": contract_id,
        "scope": scope_value,
        "repository": repo,
        "commit_sha": commit,
        "workflow_run_id": run_id,
        "job_id": parsed_job_id,
        "deployment_id": deploy_id,
        "deployment_sha": deploy_sha,
        "proof_id": proof_id,
        "conclusion": str(conclusion or "").strip().upper(),
        "frozen": bool(frozen),
    }


def classify_evidence(
    record: Mapping[str, Any],
    *,
    current_head_sha: str,
    current_main_sha: str,
    current_deployment_sha: str | None = None,
) -> dict[str, Any]:
    value = deepcopy(dict(record))
    scope = str(value.get("scope") or "").upper()

    if (
        value.get("workflow_run_id") is None
        or value.get("job_id") is None
        or not str(value.get("proof_id") or "").strip()
        or str(value.get("conclusion") or "").upper() != "SUCCESS"
    ):
        return {
            "freshness": "INCOMPLETE",
            "requires_reproof": True,
            "reason": "successful run/job/proof identity is incomplete",
        }

    commit = str(value.get("commit_sha") or "").lower()
    if not _SHA_RE.match(commit):
        return {
            "freshness": "INCOMPLETE",
            "requires_reproof": True,
            "reason": "commit identity is incomplete",
        }

    head = _full_sha(current_head_sha, field="current_head_sha")
    main = _full_sha(current_main_sha, field="current_main_sha")

    if scope == "PR_HEAD":
        if commit != head:
            return {
                "freshness": "STALE_HEAD",
                "requires_reproof": True,
                "reason": "evidence commit does not match current PR head",
            }
    elif scope == "MERGED_MAIN":
        if commit != main:
            return {
                "freshness": "STALE_MAIN",
                "requires_reproof": True,
                "reason": "evidence commit does not match current main",
            }
    elif scope == "DEPLOYMENT":
        if commit != main:
            return {
                "freshness": "STALE_MAIN",
                "requires_reproof": True,
                "reason": "deployment proof commit does not match current main",
            }
        deploy_sha = str(value.get("deployment_sha") or "").lower()
        if not _SHA_RE.match(deploy_sha) or current_deployment_sha is None:
            return {
                "freshness": "INCOMPLETE",
                "requires_reproof": True,
                "reason": "deployment identity is incomplete",
            }
        current_deploy = _full_sha(current_deployment_sha, field="current_deployment_sha")
        if deploy_sha != commit or current_deploy != commit:
            return {
                "freshness": "STALE_DEPLOYMENT",
                "requires_reproof": True,
                "reason": "deployed commit does not match evidence commit",
            }
    else:
        return {
            "freshness": "INCOMPLETE",
            "requires_reproof": True,
            "reason": "evidence scope is invalid",
        }

    return {
        "freshness": "CURRENT",
        "requires_reproof": False,
        "reason": "evidence identity matches its current certification target",
    }


def _node(node_id: str, kind: str, **identity: Any) -> dict[str, Any]:
    return {"id": node_id, "kind": kind, **identity}


def _edge(source: str, target: str, relation: str) -> dict[str, str]:
    return {"from": source, "to": target, "relation": relation}


def _build_graph(task_id: str, checkpoint_id: str, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def add_node(item: dict[str, Any]) -> None:
        existing = nodes.get(item["id"])
        if existing is not None and existing != item:
            raise EvidenceTruthFailure(f"node identity collision: {item['id']}")
        nodes[item["id"]] = item

    def add_edge(source: str, target: str, relation: str) -> None:
        edge = _edge(source, target, relation)
        if edge not in edges:
            edges.append(edge)

    checkpoint_node = f"checkpoint:{task_id}:{checkpoint_id}"
    add_node(_node(checkpoint_node, "checkpoint", task_id=task_id, checkpoint_id=checkpoint_id))

    for record in records:
        evidence_id = str(record["evidence_id"])
        contract_node = f"contract:{record['contract_id']}"
        run_node = f"run:{record['workflow_run_id']}"
        commit_node = f"commit:{record['commit_sha']}"
        proof_node = f"proof:{evidence_id}:{record['proof_id']}"

        add_node(_node(contract_node, "contract", contract_id=record["contract_id"]))
        add_node(_node(run_node, "workflow_run", workflow_run_id=record["workflow_run_id"]))
        add_node(_node(commit_node, "commit", commit_sha=record["commit_sha"], repository=record["repository"]))
        add_node(_node(
            proof_node,
            "proof",
            evidence_id=evidence_id,
            proof_id=record["proof_id"],
            freshness=record.get("freshness"),
        ))

        add_edge(checkpoint_node, contract_node, "requires_contract")
        add_edge(contract_node, run_node, "proved_by_run")

        job_id = record.get("job_id")
        if job_id is not None:
            job_node = f"job:{job_id}"
            add_node(_node(job_node, "job", job_id=job_id))
            add_edge(run_node, job_node, "contains_job")
            add_edge(job_node, commit_node, "certifies_commit")
        else:
            add_edge(run_node, commit_node, "certifies_commit")

        proof_parent = commit_node
        deployment_id = record.get("deployment_id")
        if deployment_id:
            deploy_node = f"deployment:{deployment_id}"
            add_node(_node(
                deploy_node,
                "deployment",
                deployment_id=deployment_id,
                deployment_sha=record.get("deployment_sha"),
            ))
            add_edge(commit_node, deploy_node, "deployed_as")
            proof_parent = deploy_node

        add_edge(proof_parent, proof_node, "observed_by")

        if bool(record.get("frozen")):
            freeze_node = f"freeze:{task_id}:{checkpoint_id}:{evidence_id}"
            add_node(_node(
                freeze_node,
                "freeze",
                task_id=task_id,
                checkpoint_id=checkpoint_id,
                evidence_id=evidence_id,
            ))
            add_edge(proof_node, freeze_node, "closes_checkpoint")

    return {
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": sorted(edges, key=lambda item: (item["from"], item["to"], item["relation"])),
    }


def build_truth_ledger(
    *,
    task_id: str,
    checkpoint_id: str,
    records: Sequence[Mapping[str, Any]],
    current_head_sha: str,
    current_main_sha: str,
    current_deployment_sha: str | None = None,
) -> dict[str, Any]:
    task = str(task_id or "").strip()
    checkpoint = str(checkpoint_id or "").strip()
    if not task:
        raise EvidenceTruthFailure("task_id is required")
    if not checkpoint:
        raise EvidenceTruthFailure("checkpoint_id is required")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)) or not records:
        raise EvidenceTruthFailure("truth ledger requires at least one evidence record")

    head = _full_sha(current_head_sha, field="current_head_sha")
    main = _full_sha(current_main_sha, field="current_main_sha")
    deploy = _full_sha(current_deployment_sha, field="current_deployment_sha") if current_deployment_sha else None

    classified: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in records:
        record = deepcopy(dict(raw))
        evidence_id = str(record.get("evidence_id") or "")
        if not evidence_id or evidence_id in seen_ids:
            raise EvidenceTruthFailure("evidence IDs must be non-empty and unique")
        seen_ids.add(evidence_id)
        if str(record.get("checkpoint_id") or "") != checkpoint:
            raise EvidenceTruthFailure("evidence checkpoint does not match truth ledger checkpoint")
        classification = classify_evidence(
            record,
            current_head_sha=head,
            current_main_sha=main,
            current_deployment_sha=deploy,
        )
        record.update(classification)
        if bool(record.get("frozen")) and record["freshness"] != "CURRENT":
            raise EvidenceTruthFailure("stale evidence cannot freeze a checkpoint")
        classified.append(record)

    body = {
        "version": VERSION,
        "task_id": task,
        "checkpoint_id": checkpoint,
        "anchors": {
            "current_head_sha": head,
            "current_main_sha": main,
            "current_deployment_sha": deploy,
        },
        "records": classified,
        "graph": _build_graph(task, checkpoint, classified),
        "protections": {
            "network_calls": NETWORK_CALLS,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "historical_evidence_preserved": True,
            "stale_freeze_rejected": True,
        },
    }
    body["truth_id"] = _fingerprint(body)
    validate_truth_ledger(body)
    return body


def validate_truth_ledger(ledger: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(ledger, Mapping):
        raise EvidenceTruthFailure("truth ledger must be an object")
    value = deepcopy(dict(ledger))
    supplied_truth_id = str(value.pop("truth_id", ""))
    if not supplied_truth_id:
        raise EvidenceTruthFailure("truth ledger requires truth_id")
    if value.get("version") != VERSION:
        raise EvidenceTruthFailure("unsupported truth ledger version")

    records = value.get("records")
    graph = value.get("graph")
    if not isinstance(records, list) or not records:
        raise EvidenceTruthFailure("truth ledger requires evidence records")
    if not isinstance(graph, Mapping):
        raise EvidenceTruthFailure("truth ledger requires evidence graph")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise EvidenceTruthFailure("evidence graph requires nodes and edges")

    node_ids: list[str] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            raise EvidenceTruthFailure("graph node must be an object")
        node_id = str(node.get("id") or "")
        if not node_id:
            raise EvidenceTruthFailure("graph node requires id")
        node_ids.append(node_id)
    if len(node_ids) != len(set(node_ids)):
        raise EvidenceTruthFailure("graph node IDs must be unique")
    node_set = set(node_ids)
    for edge in edges:
        if not isinstance(edge, Mapping):
            raise EvidenceTruthFailure("graph edge must be an object")
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source not in node_set or target not in node_set:
            raise EvidenceTruthFailure("dangling graph edge")
        if not str(edge.get("relation") or ""):
            raise EvidenceTruthFailure("graph edge requires relation")

    expected_truth_id = _fingerprint(value)
    if supplied_truth_id != expected_truth_id:
        raise EvidenceTruthFailure("truth ledger fingerprint mismatch")

    current = 0
    stale = 0
    incomplete = 0
    expected_truth_id = _fingerprint(value)
    if supplied_truth_id != expected_truth_id:
        raise EvidenceTruthFailure("truth ledger fingerprint mismatch")

    for record in records:
        freshness = str(record.get("freshness") or "")
        if freshness == "CURRENT":
            current += 1
        elif freshness == "INCOMPLETE":
            incomplete += 1
        elif freshness in {"STALE_HEAD", "STALE_MAIN", "STALE_DEPLOYMENT"}:
            stale += 1
        else:
            raise EvidenceTruthFailure("unknown evidence freshness")
        if bool(record.get("frozen")) and freshness != "CURRENT":
            raise EvidenceTruthFailure("stale evidence cannot freeze a checkpoint")

    return {
        "status": "GREEN",
        "truth_id": supplied_truth_id,
        "record_count": len(records),
        "current_evidence": current,
        "stale_evidence": stale,
        "incomplete_evidence": incomplete,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }
