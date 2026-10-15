-- Runless Dynamic Finalization Authority V1 — Step 3
-- Durable exact-head/idempotent publication claim for runless-final-gate.
-- This extends the existing proof_runs authority row; it does not create a second authority table.

alter table runless_v2.proof_runs
    add column if not exists gate_publication_claim_token text null,
    add column if not exists gate_publication_claimed_at timestamptz null,
    add column if not exists gate_publication_digest text null;

alter table runless_v2.proof_runs
    drop constraint if exists proof_runs_gate_publication_digest_check;

alter table runless_v2.proof_runs
    add constraint proof_runs_gate_publication_digest_check
    check (
        gate_publication_digest is null
        or gate_publication_digest ~ '^sha256:[0-9a-f]{64}$'
    );

create or replace function runless_v2.claim_final_gate_publication(
    p_proof_id text,
    p_candidate_sha text,
    p_fencing_generation bigint,
    p_proof_digest text,
    p_claim_token text
)
returns jsonb
language plpgsql
security definer
set search_path = runless_v2, public
as $$
declare
    v_run runless_v2.proof_runs%rowtype;
begin
    if coalesce(p_proof_id, '') = '' or coalesce(p_claim_token, '') = '' then
        raise exception 'RUNLESS_V2_GATE_CLAIM_IDENTITY_REQUIRED';
    end if;
    if p_candidate_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_V2_GATE_CLAIM_CANDIDATE_INVALID';
    end if;
    if p_proof_digest !~ '^sha256:[0-9a-f]{64}$' then
        raise exception 'RUNLESS_V2_GATE_CLAIM_DIGEST_INVALID';
    end if;

    select * into v_run
      from runless_v2.proof_runs
     where proof_id = p_proof_id
     for update;

    if not found then
        raise exception 'RUNLESS_V2_GATE_CLAIM_PROOF_NOT_FOUND';
    end if;
    if v_run.candidate_sha <> p_candidate_sha then
        raise exception 'RUNLESS_V2_GATE_CLAIM_CANDIDATE_MISMATCH';
    end if;
    if v_run.fencing_generation <> p_fencing_generation then
        raise exception 'RUNLESS_V2_GATE_CLAIM_STALE_FENCE';
    end if;
    if v_run.state <> 'RUNLESS_FINAL_GATE' then
        raise exception 'RUNLESS_V2_GATE_CLAIM_STATE_INVALID';
    end if;

    if v_run.gate_check_run_id is not null then
        return jsonb_build_object(
            'decision', 'EXISTING',
            'gate_check_run_id', v_run.gate_check_run_id
        );
    end if;

    if v_run.gate_publication_claim_token is not null then
        if v_run.gate_publication_digest is distinct from p_proof_digest then
            raise exception 'RUNLESS_V2_GATE_CLAIM_IDENTITY_CONFLICT';
        end if;
        return jsonb_build_object('decision', 'IN_PROGRESS');
    end if;

    update runless_v2.proof_runs
       set gate_publication_claim_token = p_claim_token,
           gate_publication_claimed_at = now(),
           gate_publication_digest = p_proof_digest,
           updated_at = now()
     where proof_id = p_proof_id;

    return jsonb_build_object(
        'decision', 'CLAIMED',
        'claim_token', p_claim_token
    );
end;
$$;

create or replace function runless_v2.complete_final_gate_publication(
    p_proof_id text,
    p_claim_token text,
    p_gate_check_run_id bigint
)
returns jsonb
language plpgsql
security definer
set search_path = runless_v2, public
as $$
declare
    v_run runless_v2.proof_runs%rowtype;
begin
    if coalesce(p_proof_id, '') = '' or coalesce(p_claim_token, '') = '' or p_gate_check_run_id <= 0 then
        raise exception 'RUNLESS_V2_GATE_COMPLETION_IDENTITY_REQUIRED';
    end if;

    select * into v_run
      from runless_v2.proof_runs
     where proof_id = p_proof_id
     for update;

    if not found then
        raise exception 'RUNLESS_V2_GATE_COMPLETION_PROOF_NOT_FOUND';
    end if;
    if v_run.gate_check_run_id is not null then
        if v_run.gate_check_run_id <> p_gate_check_run_id then
            raise exception 'RUNLESS_V2_GATE_COMPLETION_CHECK_CONFLICT';
        end if;
        return jsonb_build_object(
            'decision', 'EXISTING',
            'gate_check_run_id', v_run.gate_check_run_id
        );
    end if;
    if v_run.gate_publication_claim_token is distinct from p_claim_token then
        raise exception 'RUNLESS_V2_GATE_COMPLETION_CLAIM_MISMATCH';
    end if;

    update runless_v2.proof_runs
       set gate_check_run_id = p_gate_check_run_id,
           gate_publication_claim_token = null,
           gate_publication_claimed_at = null,
           updated_at = now()
     where proof_id = p_proof_id;

    return jsonb_build_object(
        'decision', 'COMPLETED',
        'gate_check_run_id', p_gate_check_run_id
    );
end;
$$;

create or replace function runless_v2.release_final_gate_publication(
    p_proof_id text,
    p_claim_token text
)
returns jsonb
language plpgsql
security definer
set search_path = runless_v2, public
as $$
declare
    v_run runless_v2.proof_runs%rowtype;
begin
    select * into v_run
      from runless_v2.proof_runs
     where proof_id = p_proof_id
     for update;

    if not found then
        raise exception 'RUNLESS_V2_GATE_RELEASE_PROOF_NOT_FOUND';
    end if;
    if v_run.gate_check_run_id is not null then
        return jsonb_build_object(
            'decision', 'EXISTING',
            'gate_check_run_id', v_run.gate_check_run_id
        );
    end if;
    if v_run.gate_publication_claim_token is distinct from p_claim_token then
        raise exception 'RUNLESS_V2_GATE_RELEASE_CLAIM_MISMATCH';
    end if;

    update runless_v2.proof_runs
       set gate_publication_claim_token = null,
           gate_publication_claimed_at = null,
           gate_publication_digest = null,
           updated_at = now()
     where proof_id = p_proof_id;

    return jsonb_build_object('decision', 'RELEASED');
end;
$$;

revoke all on function runless_v2.claim_final_gate_publication(text,text,bigint,text,text)
from public, anon, authenticated;
revoke all on function runless_v2.complete_final_gate_publication(text,text,bigint)
from public, anon, authenticated;
revoke all on function runless_v2.release_final_gate_publication(text,text)
from public, anon, authenticated;

grant execute on function runless_v2.claim_final_gate_publication(text,text,bigint,text,text) to service_role;
grant execute on function runless_v2.complete_final_gate_publication(text,text,bigint) to service_role;
grant execute on function runless_v2.release_final_gate_publication(text,text) to service_role;
