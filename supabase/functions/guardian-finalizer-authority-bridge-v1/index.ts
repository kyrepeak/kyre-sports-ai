const EXPECTED_CAPABILITY_SHA256 = "3d214cd4d08b60a40aff95ab547e00559dc74300b3cca2f05b6d31115f735665";
const SHA40 = /^[0-9a-f]{40}$/;
const ID = /^[A-Za-z0-9._:-]{1,200}$/;

function reply(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(digest, (b) => b.toString(16).padStart(2, "0")).join("");
}

function equal64(a: string, b: string): boolean {
  if (a.length !== 64 || b.length !== 64) return false;
  let diff = 0;
  for (let i = 0; i < 64; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function authorize(req: Request): Promise<void> {
  const capability = (req.headers.get("x-finalizer-capability") || "").trim();
  if (!capability) throw new Error("FINALIZER_CAPABILITY_REQUIRED");
  if (!equal64(await sha256(capability), EXPECTED_CAPABILITY_SHA256)) {
    throw new Error("FINALIZER_CAPABILITY_INVALID");
  }
}

function serverKey(): string {
  const modern = Deno.env.get("SUPABASE_SECRET_KEYS") || "";
  if (modern) {
    try {
      const value = String(JSON.parse(modern)?.default || "").trim();
      if (value) return value;
    } catch { /* use legacy fallback */ }
  }
  const legacy = (Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "").trim();
  if (!legacy) throw new Error("FINALIZER_BRIDGE_SERVER_KEY_MISSING");
  return legacy;
}

function dbHeaders(key: string, write = false): Record<string, string> {
  const h: Record<string, string> = {
    apikey: key,
    accept: "application/json",
    [write ? "content-profile" : "accept-profile"]: "runless_v2",
  };
  if (write) h["content-type"] = "application/json";
  if (!key.startsWith("sb_secret_")) h.authorization = `Bearer ${key}`;
  return h;
}

function baseUrl(): string {
  const value = (Deno.env.get("SUPABASE_URL") || "").trim().replace(/\/$/, "");
  if (!value) throw new Error("FINALIZER_BRIDGE_SUPABASE_URL_MISSING");
  return value;
}

async function readRows(path: string, params: Record<string, string>): Promise<Record<string, unknown>[]> {
  const url = new URL(`${baseUrl()}/rest/v1/${path}`);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const response = await fetch(url, { headers: dbHeaders(serverKey()) });
  if (!response.ok) throw new Error("FINALIZER_AUTHORITY_STORE_UNAVAILABLE");
  const body = await response.json();
  if (!Array.isArray(body)) throw new Error("FINALIZER_AUTHORITY_STORE_UNAVAILABLE");
  return body as Record<string, unknown>[];
}

async function rpc(name: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await fetch(`${baseUrl()}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: dbHeaders(serverKey(), true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let message = "FINALIZER_GATE_CLAIM_STORE_UNAVAILABLE";
    try {
      const body = await response.json();
      const dbMessage = String(body?.message || "");
      if (dbMessage.startsWith("RUNLESS_V2_")) message = dbMessage;
    } catch { /* keep generic */ }
    throw new Error(message);
  }
  let body: unknown = await response.json();
  if (Array.isArray(body)) {
    if (body.length !== 1 || typeof body[0] !== "object" || body[0] === null) {
      throw new Error("FINALIZER_GATE_CLAIM_STORE_UNAVAILABLE");
    }
    body = body[0];
  }
  if (typeof body !== "object" || body === null) {
    throw new Error("FINALIZER_GATE_CLAIM_STORE_UNAVAILABLE");
  }
  return body as Record<string, unknown>;
}

function requiredId(value: unknown, error: string): string {
  const text = String(value || "");
  if (!ID.test(text)) throw new Error(error);
  return text;
}

function requiredFence(value: unknown, error: string): number {
  const n = Number(value);
  if (!Number.isSafeInteger(n) || n < 0) throw new Error(error);
  return n;
}

async function resolveAuthority(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const workstream = requiredId(payload.workstream, "FINALIZER_AUTHORITY_REQUEST_INVALID");
  const taskId = requiredId(payload.task_id, "FINALIZER_AUTHORITY_REQUEST_INVALID");
  const candidateSha = String(payload.candidate_sha || "").toLowerCase();
  const fence = requiredFence(payload.fencing_generation, "FINALIZER_AUTHORITY_REQUEST_INVALID");
  if (!SHA40.test(candidateSha)) throw new Error("FINALIZER_AUTHORITY_REQUEST_INVALID");

  const proofs = await readRows("proof_runs", {
    select: "proof_id,task_id,workstream,candidate_sha,fencing_generation,proof_fingerprint,state,scope_lease_id",
    workstream: `eq.${workstream}`,
    task_id: `eq.${taskId}`,
    candidate_sha: `eq.${candidateSha}`,
  });
  if (proofs.length === 0) throw new Error("FINALIZER_AUTHORITY_NOT_FOUND");
  if (proofs.length !== 1) throw new Error("FINALIZER_AUTHORITY_AMBIGUOUS");
  const authority = proofs[0];
  if (Number(authority.fencing_generation) !== fence) throw new Error("FINALIZER_STALE_FENCE");
  if (String(authority.state || "") === "SUPERSEDED_BASE_DRIFT") throw new Error("FINALIZER_AUTHORITY_SUPERSEDED");

  const leases = await readRows("workstream_leases", {
    select: "workstream,owner_proof_id,fencing_generation",
    workstream: `eq.${workstream}`,
  });
  if (leases.length !== 1) throw new Error("FINALIZER_AUTHORITY_AMBIGUOUS");
  if (
    String(leases[0].owner_proof_id || "") !== String(authority.proof_id || "") ||
    Number(leases[0].fencing_generation) !== fence
  ) throw new Error("FINALIZER_STALE_FENCE");
  return authority;
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return reply({ error: "METHOD_NOT_ALLOWED" }, 405);
    await authorize(req);
    const raw = await req.json();
    if (typeof raw !== "object" || raw === null || Array.isArray(raw)) throw new Error("FINALIZER_BRIDGE_REQUEST_INVALID");
    const payload = raw as Record<string, unknown>;
    const action = String(payload.action || "");

    if (action === "health") {
      await readRows("proof_runs", { select: "proof_id", limit: "1" });
      return reply({ status: "ok", authority: "runless_v2", transport: "capability_edge" });
    }
    if (action === "resolve_authority") return reply({ authority: await resolveAuthority(payload) });
    if (action === "claim_publication") {
      const proofId = requiredId(payload.proof_id, "FINALIZER_GATE_CLAIM_REQUEST_INVALID");
      const candidateSha = String(payload.candidate_sha || "").toLowerCase();
      const fence = requiredFence(payload.fencing_generation, "FINALIZER_GATE_CLAIM_REQUEST_INVALID");
      const digest = String(payload.proof_digest || "").toLowerCase();
      const claim = String(payload.claim_token || "");
      if (!SHA40.test(candidateSha) || !/^sha256:[0-9a-f]{64}$/.test(digest) || !/^[0-9a-f]{32}$/.test(claim)) {
        throw new Error("FINALIZER_GATE_CLAIM_REQUEST_INVALID");
      }
      return reply(await rpc("claim_final_gate_publication", {
        p_proof_id: proofId,
        p_candidate_sha: candidateSha,
        p_fencing_generation: fence,
        p_proof_digest: digest,
        p_claim_token: claim,
      }));
    }
    if (action === "complete_publication") {
      const proofId = requiredId(payload.proof_id, "FINALIZER_GATE_COMPLETION_REQUEST_INVALID");
      const claim = String(payload.claim_token || "");
      const checkId = Number(payload.gate_check_run_id);
      if (!/^[0-9a-f]{32}$/.test(claim) || !Number.isSafeInteger(checkId) || checkId <= 0) {
        throw new Error("FINALIZER_GATE_COMPLETION_REQUEST_INVALID");
      }
      return reply(await rpc("complete_final_gate_publication", {
        p_proof_id: proofId,
        p_claim_token: claim,
        p_gate_check_run_id: checkId,
      }));
    }
    return reply({ error: "FINALIZER_CAPABILITY_ACTION_INVALID" }, 400);
  } catch (error) {
    const detail = error instanceof Error ? error.message : "FINALIZER_AUTHORITY_BRIDGE_UNAVAILABLE";
    const unauthorized = detail === "FINALIZER_CAPABILITY_REQUIRED" || detail === "FINALIZER_CAPABILITY_INVALID";
    return reply({ error: detail }, unauthorized ? 401 : 409);
  }
});
