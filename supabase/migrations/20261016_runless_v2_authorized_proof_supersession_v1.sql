-- Runless V2 authorized-proof supersession V1
--
-- Purpose: allow proof-before-merge review to explicitly retire merge authority
-- from an otherwise valid MERGE_AUTHORIZED proof without deleting/relabeling
-- its immutable proof history. A corrected candidate may then claim the same
-- workstream. The superseded proof remains durable evidence but is fenced from
-- every later state transition.

create or replace function runless_v2.is_merge_authority_superseded(p_detail text)
returns boolean
language sql
immutable
set search_path to pg_catalog
as $$
    select coalesce(p_detail, '') ~ '^AUTHORITY_SUPERSEDED:[0-9a-f]{40}:[A-Z0-9_.:-]{1,96}$';
$$;

create or replace function runless_v2.supersede_merge_authorized_authority(
    p_proof_id text,
    p_replacement_candidate_sha text,
    p_reason text
)
returns runless_v2.proof_runs
language plpgsql
security definer
set search_path to 'runless_v2', 'public'
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_proof runless_v2.proof_runs%rowtype;
    v_marker text;
begin
    if coalesce(p_proof_id, '') = '' then
        raise exception 'RUNLESS_V2_SUPERSESSION_PROOF_ID_REQUIRED';
    end if;
    if p_replacement_candidate_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_V2_SUPERSESSION_REPLACEMENT_CANDIDATE_INVALID';
    end if;
    if coalesce(p_reason, '') !~ '^[A-Z0-9_.:-]{1,96}$' then
        raise exception 'RUNLESS_V2_SUPERSESSION_REASON_INVALID';
    end if;

    select * into v_proof
      from runless_v2.proof_runs
     where proof_id = p_proof_id
     for update;
    if not found then
        raise exception 'RUNLESS_V2_PROOF_NOT_FOUND';
    end if;

    perform pg_advisory_xact_lock(hashtextextended(v_proof.workstream, 0));

    v_marker := 'AUTHORITY_SUPERSEDED:' || p_replacement_candidate_sha || ':' || p_reason;

    if runless_v2.is_merge_authority_superseded(v_proof.detail) then
        if v_proof.detail = v_marker then
            return v_proof;
        end if;
        raise exception 'RUNLESS_V2_SUPERSESSION_IDENTITY_CONFLICT';
    end if;

    if v_proof.state <> 'MERGE_AUTHORIZED' then
        raise exception 'RUNLESS_V2_SUPERSESSION_STATE_INVALID';
    end if;
    if v_proof.candidate_sha = p_replacement_candidate_sha then
        raise exception 'RUNLESS_V2_SUPERSESSION_REPLACEMENT_MUST_DIFFER';
    end if;

    if exists (
        select 1
          from runless_v2.workstream_leases l
         where l.workstream = v_proof.workstream
           and l.expires_at > v_now
    ) then
        raise exception 'RUNLESS_V2_SUPERSESSION_WORKSTREAM_BUSY';
    end if;

    update runless_v2.proof_runs
       set detail = v_marker,
           updated_at = v_now
     where proof_id = p_proof_id
     returning * into v_proof;

    return v_proof;
end;
$$;

create or replace function runless_v2.guard_superseded_merge_authority_transition()
returns trigger
language plpgsql
security definer
set search_path to 'runless_v2', 'public'
as $$
begin
    if old.state = 'MERGE_AUTHORIZED'
       and runless_v2.is_merge_authority_superseded(old.detail)
       and new.state is distinct from old.state then
        raise exception 'RUNLESS_V2_AUTHORITY_SUPERSEDED';
    end if;
    return new;
end;
$$;

drop trigger if exists proof_authority_supersession_guard on runless_v2.proof_runs;
create trigger proof_authority_supersession_guard
before update of state on runless_v2.proof_runs
for each row
execute function runless_v2.guard_superseded_merge_authority_transition();

-- Keep claim_workstream behavior identical to the durable Runless V2 contract,
-- except that an explicitly superseded MERGE_AUTHORIZED row no longer blocks a
-- corrected candidate from becoming the one workstream execution authority.
create or replace function runless_v2.claim_workstream(
    p_workstream text,
    p_proof_id text,
    p_task_id text,
    p_candidate_sha text,
    p_expected_main_sha text,
    p_scope_lease_id text,
    p_authorization_id text,
    p_request_fingerprint text,
    p_ttl_seconds integer
)
returns table(
    proof_id text,
    lease_token uuid,
    fencing_generation bigint,
    expires_at timestamptz,
    state text,
    reused boolean
)
language plpgsql
security definer
set search_path to 'runless_v2', 'public'
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_lease runless_v2.workstream_leases%rowtype;
    v_proof runless_v2.proof_runs%rowtype;
    v_generation bigint;
    v_token uuid;
begin
    if p_ttl_seconds is null or p_ttl_seconds <= 0 then
        raise exception 'RUNLESS_V2_BAD_TTL';
    end if;

    perform pg_advisory_xact_lock(hashtextextended(p_workstream, 0));

    select * into v_proof
      from runless_v2.proof_runs
     where runless_v2.proof_runs.proof_id = p_proof_id
     for update;

    if found then
        if v_proof.workstream <> p_workstream
           or v_proof.task_id <> p_task_id
           or v_proof.candidate_sha <> p_candidate_sha
           or coalesce(v_proof.expected_main_sha, '') <> coalesce(p_expected_main_sha, '')
           or v_proof.scope_lease_id <> p_scope_lease_id
           or v_proof.authorization_id <> p_authorization_id
           or v_proof.request_fingerprint <> p_request_fingerprint then
            raise exception 'RUNLESS_V2_PROOF_IDENTITY_CONFLICT';
        end if;
        if v_proof.state = 'GREEN_FROZEN' then
            return query select v_proof.proof_id, null::uuid, v_proof.fencing_generation,
                                null::timestamptz, v_proof.state, true;
            return;
        end if;
    end if;

    if exists (
        select 1
          from runless_v2.failed_fingerprints f
         where f.request_fingerprint = p_request_fingerprint
    ) then
        raise exception 'RUNLESS_V2_FAILED_FINGERPRINT_BLOCKED';
    end if;

    if exists (
        select 1
          from runless_v2.proof_runs p
         where p.workstream = p_workstream
           and p.proof_id <> p_proof_id
           and p.state in ('MERGE_AUTHORIZED','MERGED','POST_MERGE_VERIFY','FREEZE','READ_BACK')
           and not runless_v2.is_merge_authority_superseded(p.detail)
    ) then
        raise exception 'RUNLESS_V2_AUTHORITY_CONFLICT';
    end if;

    select * into v_lease
      from runless_v2.workstream_leases l
     where l.workstream = p_workstream
     for update;

    if found
       and v_lease.owner_proof_id = p_proof_id
       and v_lease.request_fingerprint = p_request_fingerprint
       and v_lease.expires_at > v_now then
        return query
        select p_proof_id, v_lease.lease_token, v_lease.fencing_generation,
               v_lease.expires_at, coalesce(v_proof.state, 'IDENTIFY'), true;
        return;
    end if;

    if found and v_lease.expires_at > v_now and v_lease.owner_proof_id <> p_proof_id then
        raise exception 'RUNLESS_V2_WORKSTREAM_BUSY';
    end if;

    if v_proof.proof_id is null then
        insert into runless_v2.proof_runs (
            proof_id, task_id, workstream, candidate_sha, expected_main_sha,
            scope_lease_id, authorization_id, request_fingerprint, state
        ) values (
            p_proof_id, p_task_id, p_workstream, p_candidate_sha, p_expected_main_sha,
            p_scope_lease_id, p_authorization_id, p_request_fingerprint, 'IDENTIFY'
        )
        returning * into v_proof;
    elsif v_proof.state = 'FAILED' then
        update runless_v2.proof_runs
           set state = 'IDENTIFY', failure_class = 'NONE', detail = '', terminal_at = null,
               receipt_digest = null, gate_check_run_id = null, updated_at = v_now
         where runless_v2.proof_runs.proof_id = p_proof_id
        returning * into v_proof;
    end if;

    v_generation := coalesce(v_lease.fencing_generation, 0) + 1;
    v_token := extensions.gen_random_uuid();

    insert into runless_v2.workstream_leases (
        workstream, owner_proof_id, lease_token, fencing_generation, request_fingerprint,
        acquired_at, renewed_at, expires_at, updated_at
    ) values (
        p_workstream, p_proof_id, v_token, v_generation, p_request_fingerprint,
        v_now, v_now, v_now + make_interval(secs => p_ttl_seconds), v_now
    )
    on conflict (workstream) do update
        set owner_proof_id = excluded.owner_proof_id,
            lease_token = excluded.lease_token,
            fencing_generation = runless_v2.workstream_leases.fencing_generation + 1,
            request_fingerprint = excluded.request_fingerprint,
            acquired_at = excluded.acquired_at,
            renewed_at = excluded.renewed_at,
            expires_at = excluded.expires_at,
            updated_at = excluded.updated_at
    returning runless_v2.workstream_leases.lease_token,
              runless_v2.workstream_leases.fencing_generation,
              runless_v2.workstream_leases.expires_at
         into v_token, v_generation, v_lease.expires_at;

    update runless_v2.proof_runs
       set fencing_generation = v_generation, updated_at = v_now
     where runless_v2.proof_runs.proof_id = p_proof_id;

    return query select p_proof_id, v_token, v_generation, v_lease.expires_at, v_proof.state, false;
end;
$$;

revoke all on function runless_v2.supersede_merge_authorized_authority(text,text,text) from public;
grant execute on function runless_v2.supersede_merge_authorized_authority(text,text,text) to service_role;
