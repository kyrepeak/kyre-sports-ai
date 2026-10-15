-- Runless Dynamic Finalization Authority V1 — Step 4
-- Durable terminal completion latch with resumable one-checkpoint closeout transitions.

create or replace function runless_v2.resume_closeout_green_frozen(
    p_proof_id text,
    p_candidate_sha text,
    p_merged_main_sha text,
    p_freeze_token text,
    p_proof_digest text,
    p_manifest_state_hash text
)
returns runless_v2.proof_runs
language plpgsql
security definer
set search_path = runless_v2, public
as $$
declare
    v_proof runless_v2.proof_runs%rowtype;
begin
    select * into v_proof
      from runless_v2.proof_runs
     where proof_id = p_proof_id
     for update;

    if not found then
        raise exception 'RUNLESS_V2_PROOF_NOT_FOUND';
    end if;

    perform pg_advisory_xact_lock(hashtextextended(v_proof.workstream, 0));

    if v_proof.candidate_sha <> p_candidate_sha
       or v_proof.receipt_digest <> p_proof_digest
       or p_freeze_token is null or p_freeze_token = ''
       or p_merged_main_sha !~ '^[0-9a-f]{40}$'
       or p_manifest_state_hash is null or p_manifest_state_hash = '' then
        raise exception 'RUNLESS_V2_CLOSEOUT_EVIDENCE_MISMATCH';
    end if;

    -- Terminal completion latch: exact evidence returns the durable terminal row
    -- without replaying any finalization transition.
    if v_proof.state = 'GREEN_FROZEN' then
        if v_proof.merged_main_sha is distinct from p_merged_main_sha
           or v_proof.freeze_token is distinct from p_freeze_token
           or v_proof.manifest_state_hash is distinct from p_manifest_state_hash then
            raise exception 'RUNLESS_V2_CLOSEOUT_EVIDENCE_MISMATCH';
        end if;
        return v_proof;
    end if;

    if v_proof.state = 'MERGE_AUTHORIZED' then
        if exists (
            select 1 from runless_v2.workstream_leases
             where workstream = v_proof.workstream
        ) then
            raise exception 'RUNLESS_V2_WORKSTREAM_BUSY';
        end if;
        if not runless_v2.is_legal_transition('MERGE_AUTHORIZED','MERGED') then
            raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION';
        end if;
        update runless_v2.proof_runs
           set state='MERGED', merged_main_sha=p_merged_main_sha, updated_at=clock_timestamp()
         where proof_id=p_proof_id
         returning * into v_proof;
        return v_proof;
    end if;

    if v_proof.merged_main_sha is distinct from p_merged_main_sha then
        raise exception 'RUNLESS_V2_CLOSEOUT_EVIDENCE_MISMATCH';
    end if;

    if v_proof.state = 'MERGED' then
        if not runless_v2.is_legal_transition('MERGED','POST_MERGE_VERIFY') then
            raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION';
        end if;
        update runless_v2.proof_runs
           set state='POST_MERGE_VERIFY', updated_at=clock_timestamp()
         where proof_id=p_proof_id
         returning * into v_proof;
        return v_proof;
    end if;

    if v_proof.state = 'POST_MERGE_VERIFY' then
        if not runless_v2.is_legal_transition('POST_MERGE_VERIFY','FREEZE') then
            raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION';
        end if;
        update runless_v2.proof_runs
           set state='FREEZE', freeze_token=p_freeze_token, updated_at=clock_timestamp()
         where proof_id=p_proof_id
         returning * into v_proof;
        return v_proof;
    end if;

    if v_proof.state = 'FREEZE' then
        if v_proof.freeze_token is distinct from p_freeze_token then
            raise exception 'RUNLESS_V2_CLOSEOUT_EVIDENCE_MISMATCH';
        end if;
        if not runless_v2.is_legal_transition('FREEZE','READ_BACK') then
            raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION';
        end if;
        update runless_v2.proof_runs
           set state='READ_BACK', manifest_state_hash=p_manifest_state_hash, updated_at=clock_timestamp()
         where proof_id=p_proof_id
         returning * into v_proof;
        return v_proof;
    end if;

    if v_proof.state = 'READ_BACK' then
        if v_proof.freeze_token is distinct from p_freeze_token
           or v_proof.manifest_state_hash is distinct from p_manifest_state_hash then
            raise exception 'RUNLESS_V2_CLOSEOUT_EVIDENCE_MISMATCH';
        end if;
        if not runless_v2.is_legal_transition('READ_BACK','GREEN_FROZEN') then
            raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION';
        end if;
        update runless_v2.proof_runs
           set state='GREEN_FROZEN',
               terminal_at=coalesce(terminal_at, clock_timestamp()),
               updated_at=clock_timestamp()
         where proof_id=p_proof_id
         returning * into v_proof;
        return v_proof;
    end if;

    raise exception 'RUNLESS_V2_CLOSEOUT_NON_RESUMABLE_STATE';
end;
$$;

revoke all on function runless_v2.resume_closeout_green_frozen(text,text,text,text,text,text)
from public, anon, authenticated;
grant execute on function runless_v2.resume_closeout_green_frozen(text,text,text,text,text,text)
to service_role;
