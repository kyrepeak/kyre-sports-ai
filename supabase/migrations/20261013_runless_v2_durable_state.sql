-- Runless V2 durable proof authority control state.
-- Supabase is durable execution/control-state authority; GitHub receipts + finalization ledger remain terminal proof/freeze authority.

create extension if not exists pgcrypto with schema extensions;

create schema if not exists runless_v2;

create table if not exists runless_v2.proof_runs (
    proof_id text primary key,
    task_id text not null,
    workstream text not null,
    candidate_sha text not null check (candidate_sha ~ '^[0-9a-f]{40}$'),
    expected_main_sha text null check (expected_main_sha is null or expected_main_sha ~ '^[0-9a-f]{40}$'),
    scope_lease_id text not null,
    authorization_id text not null,
    request_fingerprint text not null,
    proof_fingerprint text null,
    state text not null default 'IDENTIFY' check (state in (
        'IDENTIFY','2A_LOCK','FINGERPRINT','REUSE_OR_PROVE','PUBLIC_CHECK_IF_REQUIRED',
        'RECEIPT','RUNLESS_FINAL_GATE','MERGE_AUTHORIZED','MERGED','POST_MERGE_VERIFY',
        'FREEZE','READ_BACK','GREEN_FROZEN','FAILED'
    )),
    failure_class text not null default 'NONE',
    detail text not null default '',
    fencing_generation bigint not null default 0 check (fencing_generation >= 0),
    receipt_digest text null,
    gate_check_run_id bigint null,
    merged_main_sha text null check (merged_main_sha is null or merged_main_sha ~ '^[0-9a-f]{40}$'),
    freeze_token text null,
    manifest_state_hash text null,
    created_at timestamptz not null default clock_timestamp(),
    updated_at timestamptz not null default clock_timestamp(),
    terminal_at timestamptz null,
    unique (workstream, request_fingerprint)
);

create index if not exists runless_v2_proof_runs_workstream_state_idx
    on runless_v2.proof_runs (workstream, state);

create table if not exists runless_v2.workstream_leases (
    workstream text primary key,
    owner_proof_id text not null references runless_v2.proof_runs(proof_id) on delete cascade,
    lease_token uuid not null,
    fencing_generation bigint not null check (fencing_generation > 0),
    request_fingerprint text not null,
    acquired_at timestamptz not null,
    renewed_at timestamptz not null,
    expires_at timestamptz not null,
    updated_at timestamptz not null default clock_timestamp()
);

create table if not exists runless_v2.failed_fingerprints (
    request_fingerprint text primary key,
    workstream text not null,
    proof_id text not null references runless_v2.proof_runs(proof_id) on delete cascade,
    failure_class text not null,
    detail_digest text not null,
    created_at timestamptz not null default clock_timestamp()
);

create index if not exists runless_v2_failed_fingerprints_workstream_idx
    on runless_v2.failed_fingerprints (workstream, created_at desc);

create table if not exists runless_v2.receipt_mirrors (
    proof_id text primary key references runless_v2.proof_runs(proof_id) on delete cascade,
    receipt_digest text not null,
    candidate_sha text not null check (candidate_sha ~ '^[0-9a-f]{40}$'),
    workstream text not null,
    receipt_json jsonb not null,
    github_receipt_ref text not null,
    github_receipt_path text not null,
    created_at timestamptz not null default clock_timestamp()
);

create or replace function runless_v2.is_legal_transition(p_expected_state text, p_target_state text)
returns boolean
language sql
immutable
as $$
    select case p_expected_state
        when 'IDENTIFY' then p_target_state in ('2A_LOCK','FAILED')
        when '2A_LOCK' then p_target_state in ('FINGERPRINT','FAILED')
        when 'FINGERPRINT' then p_target_state in ('REUSE_OR_PROVE','FAILED')
        when 'REUSE_OR_PROVE' then p_target_state in ('PUBLIC_CHECK_IF_REQUIRED','FAILED')
        when 'PUBLIC_CHECK_IF_REQUIRED' then p_target_state in ('RECEIPT','FAILED')
        when 'RECEIPT' then p_target_state in ('RUNLESS_FINAL_GATE','FAILED')
        when 'RUNLESS_FINAL_GATE' then p_target_state in ('MERGE_AUTHORIZED','FAILED')
        when 'MERGE_AUTHORIZED' then p_target_state = 'MERGED'
        when 'MERGED' then p_target_state = 'POST_MERGE_VERIFY'
        when 'POST_MERGE_VERIFY' then p_target_state = 'FREEZE'
        when 'FREEZE' then p_target_state = 'READ_BACK'
        when 'READ_BACK' then p_target_state = 'GREEN_FROZEN'
        else false
    end;
$$;

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
returns table (
    proof_id text,
    lease_token uuid,
    fencing_generation bigint,
    expires_at timestamptz,
    state text,
    reused boolean
)
language plpgsql
security definer
set search_path = runless_v2, public
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

create or replace function runless_v2.renew_workstream(
    p_workstream text,
    p_proof_id text,
    p_lease_token uuid,
    p_fencing_generation bigint,
    p_ttl_seconds integer
)
returns table (lease_token uuid, fencing_generation bigint, expires_at timestamptz)
language plpgsql
security definer
set search_path = runless_v2, public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_lease runless_v2.workstream_leases%rowtype;
begin
    perform pg_advisory_xact_lock(hashtextextended(p_workstream, 0));
    select * into v_lease from runless_v2.workstream_leases
     where workstream = p_workstream for update;
    if not found
       or v_lease.owner_proof_id <> p_proof_id
       or v_lease.lease_token <> p_lease_token
       or v_lease.fencing_generation <> p_fencing_generation
       or v_lease.expires_at <= v_now then
        raise exception 'RUNLESS_V2_STALE_FENCE';
    end if;
    update runless_v2.workstream_leases
       set renewed_at = v_now,
           expires_at = v_now + make_interval(secs => p_ttl_seconds),
           updated_at = v_now
     where workstream = p_workstream
     returning runless_v2.workstream_leases.lease_token,
               runless_v2.workstream_leases.fencing_generation,
               runless_v2.workstream_leases.expires_at
          into v_lease.lease_token, v_lease.fencing_generation, v_lease.expires_at;
    return query select v_lease.lease_token, v_lease.fencing_generation, v_lease.expires_at;
end;
$$;

create or replace function runless_v2.advance_proof_state(
    p_proof_id text,
    p_expected_state text,
    p_target_state text,
    p_lease_token uuid,
    p_fencing_generation bigint,
    p_detail text default ''
)
returns runless_v2.proof_runs
language plpgsql
security definer
set search_path = runless_v2, public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_proof runless_v2.proof_runs%rowtype;
    v_lease runless_v2.workstream_leases%rowtype;
begin
    select * into v_proof from runless_v2.proof_runs where proof_id = p_proof_id for update;
    if not found then raise exception 'RUNLESS_V2_PROOF_NOT_FOUND'; end if;
    perform pg_advisory_xact_lock(hashtextextended(v_proof.workstream, 0));
    select * into v_lease from runless_v2.workstream_leases where workstream = v_proof.workstream for update;
    if not found
       or v_lease.owner_proof_id <> p_proof_id
       or v_lease.lease_token <> p_lease_token
       or v_lease.fencing_generation <> p_fencing_generation
       or v_lease.expires_at <= v_now then
        raise exception 'RUNLESS_V2_STALE_FENCE';
    end if;
    if v_proof.state <> p_expected_state
       or not runless_v2.is_legal_transition(p_expected_state, p_target_state) then
        raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION';
    end if;
    update runless_v2.proof_runs
       set state = p_target_state, detail = coalesce(p_detail,''), updated_at = v_now
     where proof_id = p_proof_id
     returning * into v_proof;
    return v_proof;
end;
$$;

create or replace function runless_v2.record_failure_and_release(
    p_proof_id text,
    p_lease_token uuid,
    p_fencing_generation bigint,
    p_failure_class text,
    p_detail text,
    p_detail_digest text,
    p_record_fingerprint boolean default true
)
returns runless_v2.proof_runs
language plpgsql
security definer
set search_path = runless_v2, public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_proof runless_v2.proof_runs%rowtype;
    v_lease runless_v2.workstream_leases%rowtype;
begin
    select * into v_proof from runless_v2.proof_runs where proof_id = p_proof_id for update;
    if not found then raise exception 'RUNLESS_V2_PROOF_NOT_FOUND'; end if;
    perform pg_advisory_xact_lock(hashtextextended(v_proof.workstream, 0));
    select * into v_lease from runless_v2.workstream_leases where workstream = v_proof.workstream for update;
    if not found
       or v_lease.owner_proof_id <> p_proof_id
       or v_lease.lease_token <> p_lease_token
       or v_lease.fencing_generation <> p_fencing_generation then
        raise exception 'RUNLESS_V2_STALE_FENCE';
    end if;

    if p_record_fingerprint then
        insert into runless_v2.failed_fingerprints (
            request_fingerprint, workstream, proof_id, failure_class, detail_digest
        ) values (
            v_proof.request_fingerprint, v_proof.workstream, p_proof_id, p_failure_class, p_detail_digest
        )
        on conflict (request_fingerprint) do nothing;
    end if;

    update runless_v2.proof_runs
       set state = 'FAILED', failure_class = p_failure_class, detail = coalesce(p_detail,''),
           terminal_at = v_now, updated_at = v_now
     where proof_id = p_proof_id
     returning * into v_proof;

    delete from runless_v2.workstream_leases
     where workstream = v_proof.workstream
       and owner_proof_id = p_proof_id
       and lease_token = p_lease_token
       and fencing_generation = p_fencing_generation;
    if not found then raise exception 'RUNLESS_V2_STALE_FENCE'; end if;
    return v_proof;
end;
$$;

create or replace function runless_v2.record_merge_authorized_and_release_execution(
    p_proof_id text,
    p_lease_token uuid,
    p_fencing_generation bigint,
    p_proof_fingerprint text,
    p_receipt_digest text,
    p_gate_check_run_id bigint,
    p_receipt_json jsonb,
    p_github_receipt_ref text,
    p_github_receipt_path text
)
returns runless_v2.proof_runs
language plpgsql
security definer
set search_path = runless_v2, public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_proof runless_v2.proof_runs%rowtype;
    v_lease runless_v2.workstream_leases%rowtype;
begin
    select * into v_proof from runless_v2.proof_runs where proof_id = p_proof_id for update;
    if not found then raise exception 'RUNLESS_V2_PROOF_NOT_FOUND'; end if;
    perform pg_advisory_xact_lock(hashtextextended(v_proof.workstream, 0));
    select * into v_lease from runless_v2.workstream_leases where workstream = v_proof.workstream for update;
    if not found
       or v_lease.owner_proof_id <> p_proof_id
       or v_lease.lease_token <> p_lease_token
       or v_lease.fencing_generation <> p_fencing_generation
       or v_lease.expires_at <= v_now then
        raise exception 'RUNLESS_V2_STALE_FENCE';
    end if;
    if v_proof.state <> 'RUNLESS_FINAL_GATE'
       or not runless_v2.is_legal_transition('RUNLESS_FINAL_GATE','MERGE_AUTHORIZED') then
        raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION';
    end if;

    insert into runless_v2.receipt_mirrors (
        proof_id, receipt_digest, candidate_sha, workstream, receipt_json,
        github_receipt_ref, github_receipt_path
    ) values (
        p_proof_id, p_receipt_digest, v_proof.candidate_sha, v_proof.workstream, p_receipt_json,
        p_github_receipt_ref, p_github_receipt_path
    )
    on conflict (proof_id) do update
       set receipt_digest = excluded.receipt_digest,
           receipt_json = excluded.receipt_json,
           github_receipt_ref = excluded.github_receipt_ref,
           github_receipt_path = excluded.github_receipt_path;

    update runless_v2.proof_runs
       set state = 'MERGE_AUTHORIZED', proof_fingerprint = p_proof_fingerprint,
           receipt_digest = p_receipt_digest, gate_check_run_id = p_gate_check_run_id,
           failure_class = 'NONE', detail = '', updated_at = v_now
     where proof_id = p_proof_id
     returning * into v_proof;

    delete from runless_v2.workstream_leases
     where workstream = v_proof.workstream
       and owner_proof_id = p_proof_id
       and lease_token = p_lease_token
       and fencing_generation = p_fencing_generation;
    if not found then raise exception 'RUNLESS_V2_STALE_FENCE'; end if;
    return v_proof;
end;
$$;

create or replace function runless_v2.closeout_green_frozen(
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
    v_now timestamptz := clock_timestamp();
    v_proof runless_v2.proof_runs%rowtype;
begin
    select * into v_proof from runless_v2.proof_runs where proof_id = p_proof_id for update;
    if not found then raise exception 'RUNLESS_V2_PROOF_NOT_FOUND'; end if;
    perform pg_advisory_xact_lock(hashtextextended(v_proof.workstream, 0));

    if v_proof.candidate_sha <> p_candidate_sha
       or v_proof.receipt_digest <> p_proof_digest
       or p_freeze_token is null or p_freeze_token = ''
       or p_merged_main_sha !~ '^[0-9a-f]{40}$'
       or p_manifest_state_hash is null or p_manifest_state_hash = '' then
        raise exception 'RUNLESS_V2_CLOSEOUT_EVIDENCE_MISMATCH';
    end if;
    if v_proof.state <> 'MERGE_AUTHORIZED' then
        raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION';
    end if;
    if exists (select 1 from runless_v2.workstream_leases where workstream = v_proof.workstream) then
        raise exception 'RUNLESS_V2_WORKSTREAM_BUSY';
    end if;

    if not runless_v2.is_legal_transition('MERGE_AUTHORIZED','MERGED') then raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION'; end if;
    update runless_v2.proof_runs set state='MERGED', merged_main_sha=p_merged_main_sha, updated_at=v_now where proof_id=p_proof_id;
    if not runless_v2.is_legal_transition('MERGED','POST_MERGE_VERIFY') then raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION'; end if;
    update runless_v2.proof_runs set state='POST_MERGE_VERIFY', updated_at=clock_timestamp() where proof_id=p_proof_id;
    if not runless_v2.is_legal_transition('POST_MERGE_VERIFY','FREEZE') then raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION'; end if;
    update runless_v2.proof_runs set state='FREEZE', freeze_token=p_freeze_token, updated_at=clock_timestamp() where proof_id=p_proof_id;
    if not runless_v2.is_legal_transition('FREEZE','READ_BACK') then raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION'; end if;
    update runless_v2.proof_runs set state='READ_BACK', manifest_state_hash=p_manifest_state_hash, updated_at=clock_timestamp() where proof_id=p_proof_id;
    if not runless_v2.is_legal_transition('READ_BACK','GREEN_FROZEN') then raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION'; end if;
    update runless_v2.proof_runs
       set state='GREEN_FROZEN', terminal_at=clock_timestamp(), updated_at=clock_timestamp()
     where proof_id=p_proof_id
     returning * into v_proof;
    return v_proof;
end;
$$;

revoke all on schema runless_v2 from public;
revoke all on schema runless_v2 from anon;
revoke all on schema runless_v2 from authenticated;
revoke all on all tables in schema runless_v2 from public;
revoke all on all tables in schema runless_v2 from anon;
revoke all on all tables in schema runless_v2 from authenticated;
revoke all on all functions in schema runless_v2 from public;
revoke all on all functions in schema runless_v2 from anon;
revoke all on all functions in schema runless_v2 from authenticated;

grant usage on schema runless_v2 to service_role;
grant select, insert, update, delete on all tables in schema runless_v2 to service_role;
grant execute on all functions in schema runless_v2 to service_role;
